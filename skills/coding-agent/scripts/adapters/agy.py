from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Callable

from .base import BaseAdapter, InputError


class AgyAdapter(BaseAdapter):
    """Adapter for Google Antigravity (agy) CLI."""

    name = "agy"

    def validate_start_args(self, args: argparse.Namespace) -> None:
        if shutil.which("agy") is None:
            raise InputError("agy CLI not found on PATH")
        if not getattr(args, "write", False) or getattr(args, "unsafe", False) or getattr(args, "resume_last", False):
            raise InputError("agy requires --write; read-only, unsafe and resume-last are not supported")
        effort = getattr(args, "effort", None)
        if effort is not None and effort not in {"low", "medium", "high"}:
            raise InputError("agy effort must be low, medium or high")

    def validate_workdir(self, workdir: Path) -> None:
        if not workdir.is_dir():
            raise InputError(f"workdir does not exist: {workdir}")

    def default_timeout(self) -> int | None:
        return 3600

    def prepare_job_options(self, options: dict, job_dir: Path, prompt: str | None) -> dict:
        schema_file = job_dir / "output-schema.json"
        if options.get("output_schema"):
            schema_content = Path(options["output_schema"]).read_text(encoding="utf-8")
        else:
            schema_content = '{"type":"object"}'
        schema_file.write_text(schema_content, encoding="utf-8")
        return {**options, "output_schema": str(schema_file)}

    def build_argv(self, job: dict) -> list[str]:
        argv = [
            "agy",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--add-dir", job["workdir"],
            "--mode", "accept-edits",
            "--sandbox",
        ]
        if job.get("output_schema"):
            argv += ["--json-schema", job["output_schema"]]
        if job.get("resume_thread_id"):
            argv += ["--conversation", job["resume_thread_id"]]
        if job.get("model"):
            argv += ["--model", job["model"]]
        if job.get("effort"):
            argv += ["--effort", job["effort"]]
        # agy's own print-timeout defaults to 5m and kills long provider turns
        # mid-flight; bound the turn by the job timeout so the two agree.
        if job.get("timeout_seconds"):
            argv += ["--print-timeout", f'{int(job["timeout_seconds"])}s']
        return argv

    def format_stdin_prompt(self, prompt_bytes: bytes) -> bytes:
        payload = {
            "event": "user",
            "message": {
                "content": prompt_bytes.decode("utf-8")
            }
        }
        return (json.dumps(payload) + "\n").encode("utf-8")

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

            reduced["thread_id"] = event.get("conversation_id") or reduced["thread_id"]
            if event.get("event") == "step_update":
                reduced["text_updates"] += bool(event.get("text_delta"))
                reduced["tool_updates"] += event.get("step_type") == "tool"
                reduced["phase"] = "investigating"
            if event.get("event") == "result":
                output = event.get("structured_output")
                reduced["final_message"] = json.dumps(output) if output is not None else event.get("response")
                reduced["phase"] = "done" if event.get("status") == "SUCCESS" else "failed"
                reduced["usage"] = event.get("usage")
                if event.get("status") != "SUCCESS":
                    reduced["errors"].append({"message": str(event.get("error") or event.get("status"))})

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
        if status == "completed":
            if observed_envelope.get("phase") != "done":
                errors.append({"message": "agy exited without a SUCCESS result"})
                return "failed", 2, errors
            return "completed", 0, errors
        return status, 2, errors

    def pre_cancel_check(
        self,
        job: dict,
        job_dir: Path,
        envelope: dict,
        candidates: tuple,
        process_alive_fn: Callable[[int | None], bool] | None = None,
        pid_belongs_fn: Callable[[int | None, Path], bool] | None = None,
    ) -> None:
        if envelope.get("status") == "lost":
            raise InputError("agy worker was lost; inspect its child/remote work before reconciling cancellation")
        if process_alive_fn and pid_belongs_fn:
            if any(process_alive_fn(pid) for pid in candidates) and not any(
                pid_belongs_fn(pid, job_dir) for pid in candidates
            ):
                raise InputError("cannot identify the live agy job safely; cancellation state remains unknown")

    def doctor(self, as_json: bool) -> int:
        report: dict = {"schema_version": 1, "ready": False, "checks": {}}
        binary = shutil.which("agy")
        report["checks"]["agy_path"] = binary
        if binary is None:
            report["next_steps"] = ["Install Antigravity CLI with `agy install` or add agy to PATH."]
            self._emit_doctor(report, as_json)
            return 2
        report["ready"] = True
        self._emit_doctor(report, as_json)
        return 0

    def _emit_doctor(self, report: dict, as_json: bool) -> None:
        if as_json:
            sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            return
        sys.stdout.write(f"ready={report['ready']}\n")
        for key, value in report["checks"].items():
            sys.stdout.write(f"{key}: {value}\n")
        for step in report.get("next_steps") or []:
            sys.stdout.write(f"next: {step}\n")
