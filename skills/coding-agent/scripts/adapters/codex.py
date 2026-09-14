from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .base import BaseAdapter, InputError


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex and TCodex CLI."""

    def __init__(self, binary: str = "codex") -> None:
        self.name = binary
        self.binary = binary

    def validate_start_args(self, args: argparse.Namespace) -> None:
        if shutil.which(self.binary) is None:
            if self.binary == "codex":
                raise InputError("codex CLI not found on PATH; install it with `npm install -g @openai/codex`")
            raise InputError(f"{self.binary} CLI not found on PATH")

    def validate_workdir(self, workdir: Path) -> None:
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

    def default_timeout(self) -> int | None:
        return None

    def prepare_job_options(self, options: dict, job_dir: Path, prompt: str | None) -> dict:
        return options

    def build_argv(self, job: dict) -> list[str]:
        argv = [self.binary, "-C", job["workdir"]]
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

    def format_stdin_prompt(self, prompt_bytes: bytes) -> bytes:
        return prompt_bytes

    def reduce_events(self, events_file: Path) -> dict:
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
            "tool_updates": 0,
            "text_updates": 0,
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
            if event_type in {"turn.failed", "error"}:
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
                reduced["text_updates"] += 1
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
                reduced["tool_updates"] += 1
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

    def check_completion(
        self,
        job: dict,
        job_dir: Path,
        status: str,
        returncode: int | None,
        prompt_delivered: bool,
        observed_envelope: dict,
    ) -> tuple[str, int, list[dict]]:
        errors: list[dict] = []
        if status == "completed" and not prompt_delivered:
            return "failed", 2, errors
        exit_code = 0 if status == "completed" else 2
        return status, exit_code, errors

    def doctor(self, as_json: bool) -> int:
        report: dict = {"schema_version": 1, "ready": False, "checks": {}}
        binary = shutil.which(self.binary)
        report["checks"][f"{self.binary}_path"] = binary
        if binary is None:
            report["next_steps"] = (
                ["Install Codex with `npm install -g @openai/codex`."]
                if self.binary == "codex"
                else ["Install TCodex and add `tcodex` to PATH."]
            )
            self._emit_doctor(report, as_json)
            return 2

        version = subprocess.run([self.binary, "--version"], capture_output=True, text=True, check=False)
        report["checks"]["version"] = version.stdout.strip() or version.stderr.strip()

        login = subprocess.run([self.binary, "login", "status"], capture_output=True, text=True, check=False)
        logged_in = login.returncode == 0
        report["checks"]["login"] = {
            "logged_in": logged_in,
            "detail": (login.stdout or login.stderr).strip(),
        }
        report["ready"] = logged_in
        report["next_steps"] = [] if logged_in else [f"Run `{self.binary} login`."]
        self._emit_doctor(report, as_json)
        return 0 if report["ready"] else 2

    def _emit_doctor(self, report: dict, as_json: bool) -> None:
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
