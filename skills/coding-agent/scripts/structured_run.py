#!/usr/bin/env python3
"""Run structured coding agents (Codex, agy) as monitored jobs with stable JSON envelopes."""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure local script directory is on sys.path for adapters package import
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from adapters import get_adapter, is_supported_agent, InputError, SUPPORTED_AGENTS

SCHEMA_VERSION = 1
STATE_DIR_ENV = "CODEX_RUN_STATE_DIR"
LEGACY_STATE_DIR_ENV = "CODEX_DELEGATE_STATE_DIR"
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timeout"}

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_FAILED = 2
EXIT_TIMEOUT = 124
EXIT_CANCELLED = 143


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state_dir() -> Path:
    explicit = os.environ.get(STATE_DIR_ENV) or os.environ.get(LEGACY_STATE_DIR_ENV)
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        base = Path(xdg)
    else:
        home = os.environ.get("HOME")
        if not home:
            raise InputError(f"set --state-dir, {STATE_DIR_ENV}, XDG_STATE_HOME, or HOME")
        base = Path(home) / ".local" / "state"
    legacy = base / "codex-delegate"
    if legacy.is_dir():
        return legacy
    return base / "codex-run"


def resolve_state_dir(value: str | None) -> Path:
    state_dir = Path(value) if value else default_state_dir()
    (state_dir / "jobs").mkdir(parents=True, exist_ok=True)
    return state_dir


def job_dir_for(state_dir: Path, job_id: str) -> Path:
    if not job_id or "/" in job_id or job_id.startswith("."):
        raise InputError(f"invalid job id: {job_id}")
    path = state_dir / "jobs" / job_id
    if not path.is_dir():
        raise InputError(f"unknown job: {job_id}")
    return path


def write_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
    os.replace(tmp.name, path)


def read_job(job_dir: Path) -> dict:
    return json.loads((job_dir / "job.json").read_text(encoding="utf-8"))


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ensure_git_repository(workdir: Path) -> None:
    get_adapter("codex").validate_workdir(workdir)


def ensure_codex_available(agent: str = "codex") -> str:
    binary = shutil.which(agent)
    if binary is None:
        if agent == "codex":
            raise InputError("codex CLI not found on PATH; install it with `npm install -g @openai/codex`")
        raise InputError(f"{agent} CLI not found on PATH")
    return binary


# --------------------------------------------------------------------------
# Event reduction
# --------------------------------------------------------------------------


def reduce_events(events_file: Path, agent: str = "codex") -> dict:
    """Fold provider events into observations, not acceptance evidence."""
    return get_adapter(agent).reduce_events(events_file)


def refresh_envelope(job: dict, job_dir: Path) -> dict:
    """Merge stored job metadata with the current event stream."""
    agent = job.get("agent", "codex")
    reduced = reduce_events(job_dir / "events.jsonl", agent)
    final_file = job_dir / "final.txt"
    final_message = reduced["final_message"]
    if final_file.is_file():
        stored = final_file.read_text(encoding="utf-8")
        if stored.strip():
            final_message = stored

    envelope = dict(job)
    envelope.update(
        {
            "thread_id": reduced["thread_id"] or job.get("thread_id"),
            "final_message": final_message,
            "touched_files": reduced["touched_files"],
            "commands": reduced["commands"],
            "usage": reduced["usage"],
            "agent_messages": reduced["agent_messages"],
            "events_file": str(job_dir / "events.jsonl"),
            "log_file": str(job_dir / "stderr.log"),
        }
    )
    if job.get("status") not in TERMINAL_STATUSES:
        envelope["phase"] = reduced["phase"]
    errors = list(job.get("errors") or [])
    errors.extend(reduced["errors"])
    envelope["errors"] = errors
    thread_id = envelope.get("thread_id")
    resume_prefix = "agy --conversation" if agent == "agy" else f"{agent} exec resume"
    envelope["resume_command"] = f"{resume_prefix} {thread_id}" if thread_id else None

    if envelope.get("status") == "running" and not process_alive(job.get("pid")):
        envelope["status"] = "lost"

    structured = None
    if job.get("output_schema") and isinstance(final_message, str) and final_message.strip():
        try:
            structured = json.loads(final_message)
        except json.JSONDecodeError:
            structured = None
    envelope["structured_output"] = structured
    events_path = job_dir / "events.jsonl"
    envelope["activity"] = {
        "event_bytes": events_path.stat().st_size if events_path.exists() else 0,
        "last_event_mtime": events_path.stat().st_mtime if events_path.exists() else None,
        "completed_commands": len(reduced["commands"]),
        "agent_messages": reduced["agent_messages"],
        "worker_alive": process_alive(job.get("pid")),
        "child_alive": process_alive(job.get("child_pid")),
        "tool_updates": reduced.get("tool_updates"),
        "text_updates": reduced.get("text_updates"),
    }
    return envelope


# --------------------------------------------------------------------------
# Command construction
# --------------------------------------------------------------------------


def build_agent_argv(job: dict) -> list[str]:
    """Construct command-line arguments using the agent adapter."""
    adapter = get_adapter(job.get("agent", "codex"))
    return adapter.build_argv(job)


# Alias for backwards compatibility
build_codex_argv = build_agent_argv


def resolve_resume_thread(state_dir: Path, workdir: Path, agent: str = "codex") -> str:
    jobs_dir = state_dir / "jobs"
    candidates = []
    for entry in jobs_dir.iterdir() if jobs_dir.is_dir() else []:
        job_file = entry / "job.json"
        if not job_file.is_file():
            continue
        try:
            job = json.loads(job_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("workdir") != str(workdir):
            continue
        if job.get("agent", "codex") != agent:
            continue
        envelope = refresh_envelope(job, entry)
        if not envelope.get("thread_id"):
            continue
        if envelope.get("status") not in TERMINAL_STATUSES:
            raise InputError(
                f"job {job.get('job_id')} is still active in {workdir}; wait or cancel it before resuming"
            )
        candidates.append((job.get("created_at", ""), envelope["thread_id"]))
    if not candidates:
        display_name = "Codex" if agent == "codex" else "TCodex"
        raise InputError(f"no previous {display_name} thread recorded for {workdir}")
    candidates.sort()
    return candidates[-1][1]


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------


class Interrupted(Exception):
    """SIGINT or SIGTERM reached the worker while running."""


def raise_interrupted(_signum: int, _frame: object) -> None:
    raise Interrupted()


def install_interrupt_handlers() -> dict[int, object]:
    previous: dict[int, object] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, raise_interrupted)
        except (ValueError, OSError):
            pass
    return previous


def restore_interrupt_handlers(previous: dict[int, object]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def deliver_prompt(proc: subprocess.Popen, prompt: bytes, deadline: float | None) -> None:
    if proc.stdin is None or not prompt:
        return
    fd = proc.stdin.fileno()
    os.set_blocking(fd, False)
    view = memoryview(prompt)
    total_sent = 0
    while total_sent < len(view):
        if deadline is not None and time.monotonic() > deadline:
            raise subprocess.TimeoutExpired(proc.args, deadline)
        timeout = max(0.0, deadline - time.monotonic()) if deadline else 1.0
        _, writable, _ = select.select([], [fd], [], timeout)
        if writable:
            sent = os.write(fd, view[total_sent:])
            total_sent += sent
    proc.stdin.close()


def finalize_job(
    job: dict,
    job_dir: Path,
    status: str,
    exit_code: int,
    codex_exit_code: int | None,
    started_monotonic: float,
) -> dict:
    finished_iso = now_iso()
    duration = time.monotonic() - started_monotonic
    job.update(
        {
            "status": status,
            "exit_code": exit_code,
            "codex_exit_code": codex_exit_code,
            "finished_at": finished_iso,
            "duration_seconds": duration,
            "pid": None,
            "child_pid": None,
        }
    )
    if not job.get("started_at"):
        job["started_at"] = finished_iso
    write_json(job_dir / "job.json", job)
    return refresh_envelope(job, job_dir)


def execute_job(job_dir: Path) -> dict:
    job = read_job(job_dir)
    if job.get("status") in TERMINAL_STATUSES:
        # A cancel can land between the background launch and this first read.
        return refresh_envelope(job, job_dir)

    events_file = job_dir / "events.jsonl"
    stderr_file = job_dir / "stderr.log"
    prompt_file = job_dir / "prompt.txt"

    adapter = get_adapter(job.get("agent", "codex"))
    argv = adapter.build_argv(job)

    job.update({"status": "running", "started_at": now_iso(), "pid": os.getpid(), "command": argv})
    write_json(job_dir / "job.json", job)

    started = time.monotonic()
    deadline = started + job["timeout_seconds"] if job.get("timeout_seconds") else None
    proc: subprocess.Popen | None = None
    previous_handlers = install_interrupt_handlers()
    try:
        with events_file.open("wb") as events, stderr_file.open("wb") as errors:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE if job.get("has_prompt") else subprocess.DEVNULL,
                stdout=events,
                stderr=errors,
                cwd=job["workdir"],
                start_new_session=True,
            )
            job["child_pid"] = proc.pid
            write_json(job_dir / "job.json", job)

            current = read_job(job_dir)
            if current.get("status") == "cancelled":
                terminate_process_group(proc.pid)
                proc.wait()
                return finalize_job(job, job_dir, "cancelled", EXIT_CANCELLED, proc.returncode, started)

            prompt_delivered = True
            if job.get("has_prompt") and proc.stdin is not None:
                try:
                    prompt_bytes = prompt_file.read_bytes()
                    prompt_payload = adapter.format_stdin_prompt(prompt_bytes)
                    deliver_prompt(proc, prompt_payload, deadline)
                except OSError as exc:
                    prompt_delivered = False
                    job.setdefault("errors", []).append(
                        {"message": f"{adapter.name} closed stdin before the prompt was delivered: {exc}"}
                    )

            try:
                returncode = proc.wait(timeout=max(0, deadline - time.monotonic()) if deadline else None)
                status = "completed" if returncode == 0 else "failed"
                exit_code = EXIT_OK if returncode == 0 else EXIT_FAILED
            except subprocess.TimeoutExpired:
                terminate_process_group(proc.pid)
                proc.wait()
                returncode = proc.returncode
                status, exit_code = "timeout", EXIT_TIMEOUT
    except subprocess.TimeoutExpired:
        if proc is not None:
            terminate_process_group(proc.pid)
            proc.wait()
        return finalize_job(job, job_dir, "timeout", EXIT_TIMEOUT, proc.returncode if proc else None, started)
    except (Interrupted, KeyboardInterrupt):
        if proc is not None:
            terminate_process_group(proc.pid)
            proc.wait()
        job.setdefault("errors", []).append({"message": "interrupted by signal"})
        return finalize_job(
            job, job_dir, "cancelled", EXIT_CANCELLED, proc.returncode if proc else None, started
        )
    finally:
        restore_interrupt_handlers(previous_handlers)

    observed = refresh_envelope(job, job_dir)
    status, exit_code, extra_errors = adapter.check_completion(
        job, job_dir, status, returncode, prompt_delivered, observed
    )
    for err in extra_errors:
        job.setdefault("errors", []).append(err)

    return finalize_job(job, job_dir, status, exit_code, returncode, started)


def signal_process_group(pid: int, sig: int) -> None:
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def terminate_process_group(pid: int, grace_seconds: float = 3.0) -> None:
    signal_process_group(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not process_alive(pid):
            return
        time.sleep(0.05)
    signal_process_group(pid, signal.SIGKILL)


def spawn_background_worker(job_dir: Path) -> int:
    argv = [sys.executable, str(Path(__file__).resolve()), "_worker", "--job-dir", str(job_dir)]
    with open(os.devnull, "rb") as devnull, (job_dir / "worker.log").open("ab") as worker_log:
        proc = subprocess.Popen(
            argv,
            stdin=devnull,
            stdout=worker_log,
            stderr=worker_log,
            start_new_session=True,
        )
    # Recorded outside job.json so it cannot race the worker's own status writes,
    # yet still lets cancel reach a worker that has not launched Codex yet.
    (job_dir / "worker.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc.pid


def read_worker_pid(job_dir: Path) -> int | None:
    path = job_dir / "worker.pid"
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def proc_argv(pid: int) -> list[str] | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\x00") if part]


def ps_command_line(pid: int) -> str | None:
    completed = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    line = completed.stdout.strip()
    return line or None


def command_line_has_token(command_line: str, token: str) -> bool:
    pos = 0
    while True:
        pos = command_line.find(token, pos)
        if pos == -1:
            return False
        left = pos == 0 or command_line[pos - 1] in (" ", "\t", "\n", "=", '"', "'")
        end = pos + len(token)
        right = end == len(command_line) or command_line[end] in (" ", "\t", "\n", '"', "'")
        if left and right:
            return True
        pos = end


def pid_belongs_to_job(pid: int | None, job_dir: Path) -> bool:
    if not pid or not process_alive(pid):
        return False
    job_dir_str = str(job_dir)
    argv = proc_argv(pid)
    if argv is not None:
        return job_dir_str in argv
    line = ps_command_line(pid)
    if line is None:
        return False
    return command_line_has_token(line, job_dir_str)


# --------------------------------------------------------------------------
# Job creation
# --------------------------------------------------------------------------


def create_job(state_dir: Path, kind: str, workdir: Path, prompt: str | None, options: dict) -> Path:
    explicit_id = options.get("job_id")
    if explicit_id:
        job_dir = state_dir / "jobs" / explicit_id
        if job_dir.exists():
            raise InputError(f"job {explicit_id} already exists")
    else:
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        prefix = f"{now}-{kind}-"
        job_dir = tempfile.mkdtemp(prefix=prefix, dir=state_dir / "jobs")
        job_dir = Path(job_dir)

    job_dir.mkdir(parents=True, exist_ok=True)
    job_id = job_dir.name

    if prompt is not None:
        (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    adapter = get_adapter(options.get("agent", "codex"))
    options = adapter.prepare_job_options(options, job_dir, prompt)

    job = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "job_dir": str(job_dir),
        "kind": kind,
        "agent": options.get("agent", "codex"),
        "status": "queued",
        "phase": "queued",
        "exit_code": None,
        "codex_exit_code": None,
        "workdir": str(workdir),
        "sandbox": options["sandbox"],
        "model": options.get("model"),
        "effort": options.get("effort"),
        "output_schema": options.get("output_schema"),
        "has_prompt": prompt is not None,
        "created_at": now_iso(),
        "started_at": None,
        "finished_at": None,
        "pid": None,
        "child_pid": None,
        "errors": [],
        "review_target": options.get("review_target"),
        "resume_thread_id": options.get("resume_thread_id"),
        "timeout_seconds": options.get("timeout_seconds"),
    }
    write_json(job_dir / "job.json", job)
    (job_dir / "events.jsonl").touch()
    (job_dir / "stderr.log").touch()
    return job_dir


def read_prompt(args: argparse.Namespace) -> str:
    if getattr(args, "prompt_file", None):
        path = Path(args.prompt_file)
        if not path.is_file():
            raise InputError(f"prompt file does not exist: {path}")
        text = path.read_text(encoding="utf-8")
    else:
        text = args.prompt or ""
    if not text.strip():
        raise InputError("prompt is empty; pass --prompt-file or --prompt with real content")
    return text


def resolve_sandbox(write: bool, unsafe: bool) -> str:
    if unsafe and write:
        raise InputError("choose either --write or --unsafe")
    if unsafe:
        return "danger-full-access"
    return "workspace-write" if write else "read-only"


# --------------------------------------------------------------------------
# Output formatting
# --------------------------------------------------------------------------


def render_envelope(envelope: dict) -> str:
    lines = [
        f"job_id: {envelope.get('job_id')}",
        f"status: {envelope.get('status')}",
        f"phase: {envelope.get('phase')}",
        f"workdir: {envelope.get('workdir')}",
    ]
    if envelope.get("model"):
        lines.append(f"model: {envelope.get('model')}")
    if envelope.get("thread_id"):
        lines.append(f"thread_id: {envelope.get('thread_id')}")
    if envelope.get("exit_code") is not None:
        lines.append(f"exit_code: {envelope.get('exit_code')}")
    for err in envelope.get("errors") or []:
        lines.append(f"error: {err.get('message') if isinstance(err, dict) else err}")
    if envelope.get("resume_command"):
        lines.append(f"resume_command: {envelope.get('resume_command')}")
    lines.append(f"events_file: {envelope.get('events_file')}")
    lines.append(f"log_file: {envelope.get('log_file')}")
    touched = envelope.get("touched_files") or []
    if touched:
        lines.append("touched_files:")
        for item in touched:
            lines.append(f"  - {item.get('path')} ({item.get('kind')})")
    commands = envelope.get("commands") or []
    if commands:
        lines.append("commands:")
        for cmd in commands:
            lines.append(f"  - {cmd.get('command')} -> {cmd.get('exit_code')}")
    if envelope.get("final_message"):
        lines.append("--- final message ---")
        lines.append(envelope["final_message"].strip())
    return "\n".join(lines) + "\n"


def emit(envelope: dict, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render_envelope(envelope))


def exit_code_for(envelope: dict) -> int:
    status = envelope.get("status")
    if status == "completed":
        return EXIT_OK
    if status == "timeout":
        return EXIT_TIMEOUT
    if status == "cancelled":
        return EXIT_CANCELLED
    return EXIT_FAILED


# --------------------------------------------------------------------------
# CLI subcommands
# --------------------------------------------------------------------------


def start_like(args: argparse.Namespace, kind: str) -> int:
    agent = getattr(args, "agent", "codex")
    adapter = get_adapter(agent)
    adapter.validate_start_args(args)

    if args.timeout is not None and args.timeout <= 0:
        raise InputError("--timeout must be positive")
    state_dir = resolve_state_dir(args.state_dir)
    workdir = Path(args.workdir).resolve()
    adapter.validate_workdir(workdir)

    options = {
        "agent": agent,
        "job_id": getattr(args, "job_id", None),
        "sandbox": resolve_sandbox(getattr(args, "write", False), getattr(args, "unsafe", False)),
        "model": getattr(args, "model", None),
        "effort": getattr(args, "effort", None),
        "timeout_seconds": args.timeout if args.timeout is not None else adapter.default_timeout(),
    }

    if kind == "review":
        prompt = None
        if args.instructions_file:
            path = Path(args.instructions_file)
            if not path.is_file():
                raise InputError(f"instructions file does not exist: {path}")
            prompt = path.read_text(encoding="utf-8")
        selected = [name for name in ("uncommitted", "base", "commit") if getattr(args, name)]
        if len(selected) > 1:
            raise InputError("choose at most one of --uncommitted, --base, --commit")
        options["review_target"] = {
            "uncommitted": args.uncommitted,
            "base": args.base,
            "commit": args.commit,
        }
        options["sandbox"] = "read-only"
    else:
        prompt = read_prompt(args)
        if args.output_schema:
            schema_path = Path(args.output_schema)
            if not schema_path.is_file():
                raise InputError(f"output schema does not exist: {schema_path}")
            options["output_schema"] = str(schema_path.resolve())
        if args.resume and args.resume_last:
            raise InputError("choose either --resume or --resume-last")
        if args.resume_last:
            options["resume_thread_id"] = resolve_resume_thread(state_dir, workdir, agent)
        elif args.resume:
            options["resume_thread_id"] = args.resume
            if agent == "agy":
                matches = []
                for job_file in (state_dir / "jobs").glob("*/job.json"):
                    recorded = read_job(job_file.parent)
                    observed = refresh_envelope(recorded, job_file.parent)
                    if observed.get("thread_id") == args.resume:
                        matches.append(observed)
                if not matches or any(
                    item.get("agent") != agent
                    or item.get("workdir") != str(workdir)
                    or item.get("status") not in TERMINAL_STATUSES
                    for item in matches
                ):
                    raise InputError("agy resume requires a recorded terminal conversation in this workdir")
        if options.get("resume_thread_id"):
            kind = "resume"

    job_dir = create_job(state_dir, kind, workdir, prompt, options)

    if args.background:
        spawn_background_worker(job_dir)
        emit(refresh_envelope(read_job(job_dir), job_dir), args.json)
        return EXIT_OK

    envelope = execute_job(job_dir)
    emit(envelope, args.json)
    return exit_code_for(envelope)


def cmd_status(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    if args.job_id:
        job_dir = job_dir_for(state_dir, args.job_id)
        envelope = refresh_envelope(read_job(job_dir), job_dir)
        if args.json:
            emit(envelope, True)
        else:
            sys.stdout.write(render_envelope(envelope))
        return EXIT_OK

    jobs = []
    jobs_dir = state_dir / "jobs"
    for entry in sorted(jobs_dir.iterdir()) if jobs_dir.is_dir() else []:
        if not (entry / "job.json").is_file():
            continue
        envelope = refresh_envelope(read_job(entry), entry)
        jobs.append(
            {
                "job_id": envelope.get("job_id"),
                "status": envelope.get("status"),
                "phase": envelope.get("phase"),
                "workdir": envelope.get("workdir"),
                "model": envelope.get("model"),
                "created_at": envelope.get("created_at"),
                "exit_code": envelope.get("exit_code"),
            }
        )
    if args.json:
        sys.stdout.write(json.dumps({"jobs": jobs}, indent=2, ensure_ascii=False) + "\n")
    else:
        for item in jobs:
            sys.stdout.write(
                f"{item['job_id']}\t{item['status']}\t{item['phase']}\t{item['workdir']}\t{item.get('model') or '-'}\n"
            )
    return EXIT_OK


def cmd_result(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    envelope = refresh_envelope(read_job(job_dir), job_dir)
    emit(envelope, args.json)
    return exit_code_for(envelope)


def cmd_wait(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    deadline = time.monotonic() + args.timeout if args.timeout else None
    poll_interval = 0.5
    while True:
        job = read_job(job_dir)
        envelope = refresh_envelope(job, job_dir)
        if envelope.get("status") in TERMINAL_STATUSES:
            emit(envelope, args.json)
            return exit_code_for(envelope)
        if deadline is not None and time.monotonic() >= deadline:
            emit(envelope, args.json)
            return EXIT_TIMEOUT
        time.sleep(poll_interval)


def cmd_logs(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    if args.raw:
        events_file = job_dir / "events.jsonl"
        if events_file.is_file():
            sys.stdout.write(events_file.read_text(encoding="utf-8", errors="replace"))
        return EXIT_OK
    stderr_file = job_dir / "stderr.log"
    if stderr_file.is_file():
        text = stderr_file.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            sys.stdout.write("--- stderr ---\n")
            sys.stdout.write(text)
    return EXIT_OK


def cmd_cancel(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    job = read_job(job_dir)
    if job.get("status") in TERMINAL_STATUSES:
        emit(refresh_envelope(job, job_dir), args.json)
        return EXIT_OK

    candidates = (job.get("child_pid"), read_worker_pid(job_dir), job.get("pid"))
    envelope = refresh_envelope(job, job_dir)
    adapter = get_adapter(job.get("agent", "codex"))
    adapter.pre_cancel_check(
        job,
        job_dir,
        envelope,
        candidates,
        process_alive_fn=process_alive,
        pid_belongs_fn=pid_belongs_to_job,
    )

    write_json(
        job_dir / "job.json",
        {**job, "status": "cancelled", "phase": "cancelled", "exit_code": EXIT_CANCELLED},
    )

    for candidate in candidates:
        if pid_belongs_to_job(candidate, job_dir):
            terminate_process_group(int(candidate))
            break
    job = read_job(job_dir)
    job.update(
        {
            "status": "cancelled",
            "phase": "cancelled",
            "exit_code": EXIT_CANCELLED,
            "finished_at": now_iso(),
            "pid": None,
            "child_pid": None,
        }
    )
    write_json(job_dir / "job.json", job)
    emit(refresh_envelope(job, job_dir), args.json)
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    agent = getattr(args, "agent", "codex")
    adapter = get_adapter(agent)
    return adapter.doctor(args.json)


def cmd_worker(args: argparse.Namespace) -> int:
    job_dir = Path(args.job_dir)
    try:
        envelope = execute_job(job_dir)
    finally:
        (job_dir / "worker.pid").unlink(missing_ok=True)
    return exit_code_for(envelope)


# --------------------------------------------------------------------------
# Parser and entrypoint
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="structured_run.py",
        description="Run Codex or agy as a monitored job with a stable JSON result envelope.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--state-dir")
        target.add_argument("--json", action="store_true")

    start = sub.add_parser("start", help="run a structured Codex, TCodex or agy task")
    start.add_argument("--workdir", required=True)
    start.add_argument("--agent", choices=["codex", "tcodex", "agy"], default="codex")
    start.add_argument("--job-id", help="reserve an explicit local job identity; existing ids are refused")
    start.add_argument("--prompt-file")
    start.add_argument("--prompt")
    start.add_argument("--write", action="store_true", help="allow workspace-write edits")
    start.add_argument("--unsafe", action="store_true", help="bypass approvals and sandbox")
    start.add_argument("--model")
    start.add_argument("--effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    start.add_argument("--output-schema")
    start.add_argument("--resume", help="resume an explicit Codex thread id")
    start.add_argument("--resume-last", action="store_true", help="resume the newest thread for this workdir")
    start.add_argument("--background", action="store_true")
    start.add_argument("--timeout", type=int, help="kill the Codex process after N seconds")
    add_common(start)

    review = sub.add_parser("review", help="run the built-in Codex-compatible reviewer")
    review.add_argument("--workdir", required=True)
    review.add_argument("--agent", choices=["codex", "tcodex"], default="codex")
    review.add_argument("--uncommitted", action="store_true")
    review.add_argument("--base")
    review.add_argument("--commit")
    review.add_argument("--instructions-file")
    review.add_argument("--model")
    review.add_argument("--background", action="store_true")
    review.add_argument("--timeout", type=int)
    add_common(review)

    status = sub.add_parser("status", help="list jobs or show one job")
    status.add_argument("job_id", nargs="?")
    add_common(status)

    result = sub.add_parser("result", help="print the result envelope for a job")
    result.add_argument("job_id")
    add_common(result)

    wait = sub.add_parser("wait", help="block until a job reaches a terminal state")
    wait.add_argument("job_id")
    wait.add_argument("--timeout", type=int)
    add_common(wait)

    logs = sub.add_parser("logs", help="print codex stderr and optionally the raw event stream")
    logs.add_argument("job_id")
    logs.add_argument("--raw", action="store_true")
    logs.add_argument("--state-dir")

    cancel = sub.add_parser("cancel", help="terminate an active job")
    cancel.add_argument("job_id")
    add_common(cancel)

    doctor = sub.add_parser("doctor", help="check a local Codex-compatible installation")
    doctor.add_argument("--agent", choices=["codex", "tcodex", "agy"], default="codex", help="agent to check (default: codex)")
    doctor.add_argument("--json", action="store_true")

    worker = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("--job-dir", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "start": lambda: start_like(args, "task"),
        "review": lambda: start_like(args, "review"),
        "status": lambda: cmd_status(args),
        "result": lambda: cmd_result(args),
        "wait": lambda: cmd_wait(args),
        "logs": lambda: cmd_logs(args),
        "cancel": lambda: cmd_cancel(args),
        "doctor": lambda: cmd_doctor(args),
        "_worker": lambda: cmd_worker(args),
    }
    try:
        return handlers[args.command]()
    except InputError as exc:
        sys.stderr.write(f"E_INPUT: {exc}\n")
        return EXIT_INPUT


if __name__ == "__main__":
    sys.exit(main())
