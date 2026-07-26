#!/usr/bin/env python3
"""Run Codex CLI as a monitored job and return a stable JSON result envelope."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
STATE_DIR_ENV = "CODEX_DELEGATE_STATE_DIR"
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timeout"}

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_FAILED = 2
EXIT_TIMEOUT = 124
EXIT_CANCELLED = 143


class InputError(Exception):
    """Caller supplied an unusable request."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state_dir() -> Path:
    explicit = os.environ.get(STATE_DIR_ENV)
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "codex-delegate"
    home = os.environ.get("HOME")
    if not home:
        raise InputError(
            f"set --state-dir, {STATE_DIR_ENV}, XDG_STATE_HOME, or HOME"
        )
    return Path(home) / ".local" / "state" / "codex-delegate"


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
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


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
    if shutil.which("git") is None:
        raise InputError("git is not installed; Codex requires a Git repository")
    probe = subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise InputError(
            f"{workdir} is not inside a Git repository; create an isolated worktree "
            "or initialize Git for scratch work before delegating to Codex"
        )


def ensure_codex_available() -> str:
    binary = shutil.which("codex")
    if binary is None:
        raise InputError("codex CLI not found on PATH; install it with `npm install -g @openai/codex`")
    return binary


# --------------------------------------------------------------------------
# Event reduction
# --------------------------------------------------------------------------


def reduce_events(events_file: Path) -> dict:
    """Fold the `codex exec --json` event stream into the result envelope fields."""
    reduced: dict = {
        "thread_id": None,
        "final_message": None,
        "agent_messages": 0,
        "touched_files": [],
        "commands": [],
        "usage": None,
        "phase": None,
        "errors": [],
        "unparsed_lines": 0,
    }
    if not events_file.is_file():
        return reduced

    seen_files: set[tuple[str, str]] = set()
    for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            reduced["unparsed_lines"] += 1
            continue
        if not isinstance(event, dict):
            reduced["unparsed_lines"] += 1
            continue

        event_type = str(event.get("type", ""))
        if event_type == "thread.started":
            reduced["thread_id"] = event.get("thread_id") or reduced["thread_id"]
            reduced["phase"] = "starting"
            continue
        if event_type == "turn.completed":
            usage = event.get("usage")
            if isinstance(usage, dict):
                reduced["usage"] = usage
            reduced["phase"] = "done"
            continue
        if event_type == "turn.failed" or event_type == "error":
            reduced["errors"].append(event.get("error") or event)
            reduced["phase"] = "failed"
            continue
        if event_type not in {"item.started", "item.completed", "item.updated"}:
            continue

        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))

        if item_type == "agent_message":
            if event_type == "item.completed":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    reduced["final_message"] = text
                    reduced["agent_messages"] += 1
            continue
        if item_type == "file_change":
            reduced["phase"] = "editing"
            if event_type == "item.completed":
                for change in item.get("changes") or []:
                    if not isinstance(change, dict):
                        continue
                    path = change.get("path")
                    kind = change.get("kind", "unknown")
                    if not isinstance(path, str):
                        continue
                    key = (path, str(kind))
                    if key in seen_files:
                        continue
                    seen_files.add(key)
                    reduced["touched_files"].append({"path": path, "kind": str(kind)})
            continue
        if item_type == "command_execution":
            reduced["phase"] = "running"
            if event_type == "item.completed":
                reduced["commands"].append(
                    {
                        "command": item.get("command"),
                        "exit_code": item.get("exit_code"),
                        "status": item.get("status"),
                    }
                )
            continue
        if item_type == "error":
            reduced["errors"].append(item)
            reduced["phase"] = "failed"
            continue
        if item_type in {"web_search", "mcp_tool_call", "todo_list", "reasoning"}:
            reduced["phase"] = "investigating"

    return reduced


def refresh_envelope(job: dict, job_dir: Path) -> dict:
    """Merge stored job metadata with the current event stream."""
    reduced = reduce_events(job_dir / "events.jsonl")
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
    envelope["resume_command"] = f"codex exec resume {thread_id}" if thread_id else None

    if envelope.get("status") == "running" and not process_alive(job.get("pid")):
        envelope["status"] = "lost"

    structured = None
    if job.get("output_schema") and isinstance(final_message, str) and final_message.strip():
        try:
            structured = json.loads(final_message)
        except json.JSONDecodeError:
            structured = None
    envelope["structured_output"] = structured
    return envelope


# --------------------------------------------------------------------------
# Command construction
# --------------------------------------------------------------------------


def build_codex_argv(job: dict) -> list[str]:
    argv = ["codex", "-C", job["workdir"]]
    if job["sandbox"] == "danger-full-access":
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        argv += ["-s", job["sandbox"], "-a", "never"]
    if job.get("model"):
        argv += ["-m", job["model"]]
    if job.get("effort"):
        argv += ["-c", f'model_reasoning_effort="{job["effort"]}"']
    argv.append("exec")

    if job["kind"] == "review":
        argv.append("review")
    elif job["kind"] == "resume":
        argv += ["resume", job["resume_thread_id"]]

    argv += ["--json", "-o", str(Path(job["job_dir"]) / "final.txt")]
    if job.get("output_schema"):
        argv += ["--output-schema", job["output_schema"]]

    if job["kind"] == "review":
        target = job.get("review_target") or {}
        if target.get("uncommitted"):
            argv.append("--uncommitted")
        elif target.get("base"):
            argv += ["--base", target["base"]]
        elif target.get("commit"):
            argv += ["--commit", target["commit"]]
        if job.get("has_prompt"):
            argv.append("-")
    else:
        argv.append("-")
    return argv


def resolve_resume_thread(state_dir: Path, workdir: Path) -> str:
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
        envelope = refresh_envelope(job, entry)
        if not envelope.get("thread_id"):
            continue
        if envelope.get("status") in {"queued", "running"}:
            raise InputError(
                f"job {job.get('job_id')} is still active in {workdir}; wait or cancel it before resuming"
            )
        candidates.append((job.get("created_at", ""), envelope["thread_id"]))
    if not candidates:
        raise InputError(f"no previous Codex thread recorded for {workdir}")
    candidates.sort()
    return candidates[-1][1]


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------


class Interrupted(Exception):
    """SIGINT or SIGTERM reached the worker while Codex was running."""


def raise_interrupted(_signum: int, _frame: object) -> None:
    raise Interrupted()


def install_interrupt_handlers() -> dict[int, object]:
    previous: dict[int, object] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, raise_interrupted)
        except ValueError:
            pass
    return previous


def restore_interrupt_handlers(previous: dict[int, object]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, TypeError):
            pass


def finalize_job(
    job: dict,
    job_dir: Path,
    status: str,
    exit_code: int,
    returncode: int | None,
    started: float | None,
) -> dict:
    if status != "cancelled" and read_job(job_dir).get("status") == "cancelled":
        status, exit_code = "cancelled", EXIT_CANCELLED
    job.update(
        {
            "status": status,
            "exit_code": exit_code,
            "codex_exit_code": returncode,
            "finished_at": now_iso(),
            "duration_ms": int((time.monotonic() - started) * 1000) if started is not None else None,
            "pid": None,
            "child_pid": None,
            "phase": "done" if status == "completed" else status,
        }
    )
    write_json(job_dir / "job.json", job)
    return refresh_envelope(job, job_dir)


def execute_job(job_dir: Path) -> dict:
    job = read_job(job_dir)
    if job.get("status") in TERMINAL_STATUSES:
        # A cancel can land between the background launch and this first read.
        return refresh_envelope(job, job_dir)

    argv = build_codex_argv(job)
    prompt_file = job_dir / "prompt.txt"
    events_file = job_dir / "events.jsonl"
    stderr_file = job_dir / "stderr.log"

    job.update({"status": "running", "started_at": now_iso(), "pid": os.getpid(), "command": argv})
    write_json(job_dir / "job.json", job)

    started = time.monotonic()
    proc: subprocess.Popen | None = None
    # Handlers go up before the launch so a signal can never orphan Codex.
    previous_handlers = install_interrupt_handlers()
    try:
        with events_file.open("wb") as events, stderr_file.open("wb") as errors:
            stdin_source = subprocess.PIPE if job.get("has_prompt") else subprocess.DEVNULL
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=job["workdir"],
                    stdin=stdin_source,
                    stdout=events,
                    stderr=errors,
                    start_new_session=True,
                )
            except OSError as exc:
                job.setdefault("errors", []).append({"message": f"cannot launch codex: {exc}"})
                return finalize_job(job, job_dir, "failed", EXIT_FAILED, None, started)

            job["child_pid"] = proc.pid
            write_json(job_dir / "job.json", job)

            if read_job(job_dir).get("status") == "cancelled":
                terminate_process_group(proc.pid)
                proc.wait()
                return finalize_job(job, job_dir, "cancelled", EXIT_CANCELLED, proc.returncode, started)

            prompt_delivered = True
            if job.get("has_prompt") and proc.stdin is not None:
                try:
                    proc.stdin.write(prompt_file.read_bytes())
                    proc.stdin.close()
                except OSError as exc:
                    prompt_delivered = False
                    job.setdefault("errors", []).append(
                        {"message": f"codex closed stdin before the prompt was delivered: {exc}"}
                    )

            timeout = job.get("timeout_seconds")
            try:
                returncode = proc.wait(timeout=timeout if timeout else None)
                status = "completed" if returncode == 0 else "failed"
                exit_code = EXIT_OK if returncode == 0 else EXIT_FAILED
            except subprocess.TimeoutExpired:
                terminate_process_group(proc.pid)
                proc.wait()
                returncode = proc.returncode
                status, exit_code = "timeout", EXIT_TIMEOUT
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

    if status == "completed" and not prompt_delivered:
        status, exit_code = "failed", EXIT_FAILED

    return finalize_job(job, job_dir, status, exit_code, returncode, started)


def signal_process_group(pid: int, sig: int) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def terminate_process_group(pid: int, grace_seconds: float = 3.0) -> None:
    """SIGTERM the group, then SIGKILL it so wrapper shells cannot orphan children."""
    signal_process_group(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not process_alive(pid):
            break
        time.sleep(0.1)
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
    except ValueError:
        return None


def process_command_line(pid: int) -> str | None:
    proc_file = Path(f"/proc/{pid}/cmdline")
    try:
        return proc_file.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        pass
    listing = subprocess.run(
        ["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    return listing.stdout if listing.returncode == 0 else None


def pid_belongs_to_job(pid: int | None, job_dir: Path) -> bool:
    """Guard against PID reuse: both the worker and Codex carry the job dir in argv."""
    if not pid or not process_alive(pid):
        return False
    cmdline = process_command_line(int(pid))
    return bool(cmdline) and str(job_dir) in cmdline


# --------------------------------------------------------------------------
# Job creation
# --------------------------------------------------------------------------


def create_job(state_dir: Path, kind: str, workdir: Path, prompt: str | None, options: dict) -> Path:
    job_id = f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    job_dir = state_dir / "jobs" / job_id
    suffix = 0
    while job_dir.exists():
        suffix += 1
        job_dir = state_dir / "jobs" / f"{job_id}-{suffix}"
    job_dir.mkdir(parents=True)
    job_id = job_dir.name

    if prompt is not None:
        (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    job = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "job_dir": str(job_dir),
        "kind": kind,
        "status": "queued",
        "phase": "queued",
        "exit_code": None,
        "codex_exit_code": None,
        "workdir": str(workdir),
        "sandbox": options["sandbox"],
        "model": options.get("model"),
        "effort": options.get("effort"),
        "output_schema": options.get("output_schema"),
        "resume_thread_id": options.get("resume_thread_id"),
        "review_target": options.get("review_target"),
        "timeout_seconds": options.get("timeout_seconds"),
        "has_prompt": prompt is not None,
        "prompt_chars": len(prompt) if prompt is not None else 0,
        "created_at": now_iso(),
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "pid": None,
        "child_pid": None,
        "command": None,
        "thread_id": None,
        "errors": [],
    }
    write_json(job_dir / "job.json", job)
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
# Rendering
# --------------------------------------------------------------------------


def render_envelope(envelope: dict) -> str:
    lines = [
        f"job_id={envelope['job_id']} kind={envelope['kind']} status={envelope['status']}"
        f" exit_code={envelope.get('exit_code')}",
        f"workdir={envelope['workdir']} sandbox={envelope['sandbox']}",
    ]
    if envelope.get("thread_id"):
        lines.append(f"thread_id={envelope['thread_id']} resume=\"{envelope['resume_command']}\"")
    if envelope.get("duration_ms") is not None:
        lines.append(f"duration_ms={envelope['duration_ms']}")
    usage = envelope.get("usage") or {}
    if usage:
        lines.append(
            f"tokens in={usage.get('input_tokens')} cached={usage.get('cached_input_tokens')}"
            f" out={usage.get('output_tokens')}"
        )
    touched = envelope.get("touched_files") or []
    if touched:
        lines.append("touched_files:")
        lines += [f"  {entry['kind']} {entry['path']}" for entry in touched]
    commands = envelope.get("commands") or []
    if commands:
        failed = [entry for entry in commands if entry.get("exit_code") not in (0, None)]
        lines.append(f"commands={len(commands)} failed={len(failed)}")
    for error in envelope.get("errors") or []:
        message = error.get("message") if isinstance(error, dict) else str(error)
        lines.append(f"error: {message}")
    lines.append(f"events_file={envelope.get('events_file')}")
    if envelope.get("final_message"):
        lines.append("--- final message ---")
        lines.append(envelope["final_message"].rstrip())
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
    if status in {"queued", "running"}:
        return EXIT_OK
    return EXIT_FAILED


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def start_like(args: argparse.Namespace, kind: str) -> int:
    ensure_codex_available()
    state_dir = resolve_state_dir(args.state_dir)
    workdir = Path(args.workdir).resolve()
    if not workdir.is_dir():
        raise InputError(f"workdir does not exist: {workdir}")
    ensure_git_repository(workdir)

    options = {
        "sandbox": resolve_sandbox(getattr(args, "write", False), getattr(args, "unsafe", False)),
        "model": getattr(args, "model", None),
        "effort": getattr(args, "effort", None),
        "timeout_seconds": args.timeout,
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
            options["resume_thread_id"] = resolve_resume_thread(state_dir, workdir)
        elif args.resume:
            options["resume_thread_id"] = args.resume
        if options.get("resume_thread_id"):
            kind = "resume"

    job_dir = create_job(state_dir, kind, workdir, prompt, options)

    if args.background:
        # The worker records its own pid; writing it here would race its first status update.
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
                "job_id": envelope["job_id"],
                "kind": envelope["kind"],
                "status": envelope["status"],
                "phase": envelope.get("phase"),
                "workdir": envelope["workdir"],
                "thread_id": envelope.get("thread_id"),
                "created_at": envelope.get("created_at"),
            }
        )
    jobs.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    if args.json:
        sys.stdout.write(
            json.dumps({"schema_version": SCHEMA_VERSION, "state_dir": str(state_dir), "jobs": jobs}, indent=2)
            + "\n"
        )
    elif not jobs:
        sys.stdout.write(f"no jobs in {state_dir}\n")
    else:
        for job in jobs:
            sys.stdout.write(
                f"{job['job_id']} status={job['status']} phase={job.get('phase')} kind={job['kind']}\n"
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
    while True:
        envelope = refresh_envelope(read_job(job_dir), job_dir)
        status = envelope["status"]
        if status in TERMINAL_STATUSES or status == "lost":
            emit(envelope, args.json)
            return EXIT_FAILED if status == "lost" else exit_code_for(envelope)
        if deadline is not None and time.monotonic() >= deadline:
            envelope["wait_timed_out"] = True
            emit(envelope, args.json)
            return EXIT_TIMEOUT
        time.sleep(1.0)


def cmd_logs(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    if args.raw:
        events = job_dir / "events.jsonl"
        if events.is_file():
            sys.stdout.write(events.read_text(encoding="utf-8", errors="replace"))
    stderr_file = job_dir / "stderr.log"
    if stderr_file.is_file():
        text = stderr_file.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            sys.stdout.write("--- codex stderr ---\n")
            sys.stdout.write(text)
    return EXIT_OK


def cmd_cancel(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir(args.state_dir)
    job_dir = job_dir_for(state_dir, args.job_id)
    job = read_job(job_dir)
    if job.get("status") in TERMINAL_STATUSES:
        emit(refresh_envelope(job, job_dir), args.json)
        return EXIT_OK

    # Mark the job first so a worker that is still starting refuses to launch Codex.
    write_json(
        job_dir / "job.json",
        {**job, "status": "cancelled", "phase": "cancelled", "exit_code": EXIT_CANCELLED},
    )

    # Prefer the Codex process group; the worker traps the signal and finalizes.
    for candidate in (job.get("child_pid"), read_worker_pid(job_dir), job.get("pid")):
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
    report: dict = {"schema_version": SCHEMA_VERSION, "ready": False, "checks": {}}
    binary = shutil.which("codex")
    report["checks"]["codex_path"] = binary
    if binary is None:
        report["next_steps"] = ["Install Codex with `npm install -g @openai/codex`."]
        emit_doctor(report, args.json)
        return EXIT_FAILED

    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False)
    report["checks"]["version"] = version.stdout.strip() or version.stderr.strip()

    login = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, check=False)
    logged_in = login.returncode == 0
    report["checks"]["login"] = {
        "logged_in": logged_in,
        "detail": (login.stdout or login.stderr).strip(),
    }
    report["ready"] = logged_in
    report["next_steps"] = [] if logged_in else ["Run `codex login` (or `codex login --device-auth`)."]
    emit_doctor(report, args.json)
    return EXIT_OK if report["ready"] else EXIT_FAILED


def emit_doctor(report: dict, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return
    sys.stdout.write(f"ready={report['ready']}\n")
    for key, value in report["checks"].items():
        if isinstance(value, dict):
            rendered = " ".join(f"{name}={item}" for name, item in value.items())
        else:
            rendered = str(value)
        sys.stdout.write(f"{key}: {rendered}\n")
    for step in report.get("next_steps") or []:
        sys.stdout.write(f"next: {step}\n")


def cmd_worker(args: argparse.Namespace) -> int:
    job_dir = Path(args.job_dir)
    try:
        envelope = execute_job(job_dir)
    finally:
        (job_dir / "worker.pid").unlink(missing_ok=True)
    return exit_code_for(envelope)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex_run.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--state-dir")
        target.add_argument("--json", action="store_true")

    start = sub.add_parser("start", help="run a Codex task")
    start.add_argument("--workdir", required=True)
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

    review = sub.add_parser("review", help="run the built-in Codex reviewer")
    review.add_argument("--workdir", required=True)
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

    doctor = sub.add_parser("doctor", help="check the local Codex installation")
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
    except KeyboardInterrupt:
        return EXIT_CANCELLED


if __name__ == "__main__":
    sys.exit(main())
