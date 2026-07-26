import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "codex-delegate" / "scripts" / "codex_run.py"

FAKE_CODEX = """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" > "$FAKE_CODEX_ARGV"
out=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "-o" ]]; then out="$arg"; fi
  prev="$arg"
done
cat > "$FAKE_CODEX_STDIN"
echo '{"type":"thread.started","thread_id":"thread-fixture"}'
echo '{"type":"turn.started"}'
echo '{"type":"item.completed","item":{"id":"i1","type":"file_change","changes":[{"path":"a.txt","kind":"add"}],"status":"completed"}}'
echo '{"type":"item.completed","item":{"id":"i2","type":"command_execution","command":"pytest -q","exit_code":0,"status":"completed"}}'
echo '{"type":"item.completed","item":{"id":"i3","type":"agent_message","text":"FIXTURE DONE"}}'
echo '{"type":"turn.completed","usage":{"input_tokens":11,"output_tokens":3}}'
echo 'fixture stderr line' >&2
if [[ -n "$out" ]]; then printf 'FIXTURE DONE' > "$out"; fi
exit ${FAKE_CODEX_EXIT:-0}
"""

SLOW_CODEX = """#!/usr/bin/env bash
set -u
cat > /dev/null
echo '{"type":"thread.started","thread_id":"slow-thread"}'
exec sleep 60
"""


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["FAKE_CODEX_ARGV"] = str(tmp_path / "argv.txt")
    env["FAKE_CODEX_STDIN"] = str(tmp_path / "stdin.txt")
    return {
        "tmp": tmp_path,
        "bin": bin_dir,
        "repo": repo,
        "state": tmp_path / "state",
        "env": env,
    }


def install_codex(workspace: dict, body: str = FAKE_CODEX) -> None:
    path = workspace["bin"] / "codex"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run(workspace: dict, *args: object, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), *(str(arg) for arg in args), "--state-dir", str(workspace["state"])],
        capture_output=True,
        text=True,
        env=workspace["env"],
        check=check,
    )


def start_json(workspace: dict, *args: object) -> dict:
    result = run(workspace, "start", "--workdir", workspace["repo"], *args, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def codex_argv(workspace: dict) -> str:
    return Path(workspace["env"]["FAKE_CODEX_ARGV"]).read_text(encoding="utf-8").strip()


def test_start_reduces_events_into_the_result_envelope(workspace: dict):
    install_codex(workspace)

    envelope = start_json(workspace, "--prompt", "implement the fixture")

    assert envelope["schema_version"] == 1
    assert envelope["status"] == "completed"
    assert envelope["exit_code"] == 0
    assert envelope["kind"] == "task"
    assert envelope["thread_id"] == "thread-fixture"
    assert envelope["resume_command"] == "codex exec resume thread-fixture"
    assert envelope["final_message"] == "FIXTURE DONE"
    assert envelope["touched_files"] == [{"path": "a.txt", "kind": "add"}]
    assert envelope["commands"] == [{"command": "pytest -q", "exit_code": 0, "status": "completed"}]
    assert envelope["usage"] == {"input_tokens": 11, "output_tokens": 3}
    assert envelope["errors"] == []
    assert Path(workspace["env"]["FAKE_CODEX_STDIN"]).read_text(encoding="utf-8") == "implement the fixture"


def test_read_only_is_the_default_and_write_is_explicit(workspace: dict):
    install_codex(workspace)

    envelope = start_json(workspace, "--prompt", "look around")
    assert envelope["sandbox"] == "read-only"
    assert "-s read-only -a never" in codex_argv(workspace)

    envelope = start_json(workspace, "--prompt", "change things", "--write")
    assert envelope["sandbox"] == "workspace-write"
    assert "-s workspace-write -a never" in codex_argv(workspace)


def test_unsafe_bypasses_sandbox_only_when_requested(workspace: dict):
    install_codex(workspace)

    envelope = start_json(workspace, "--prompt", "trusted worktree", "--unsafe")

    assert envelope["sandbox"] == "danger-full-access"
    argv = codex_argv(workspace)
    assert "--dangerously-bypass-approvals-and-sandbox" in argv
    assert "-s read-only" not in argv


def test_write_and_unsafe_are_mutually_exclusive(workspace: dict):
    install_codex(workspace)

    result = run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "x", "--write", "--unsafe")

    assert result.returncode == 1
    assert "E_INPUT: choose either --write or --unsafe" in result.stderr


def test_global_flags_precede_the_exec_subcommand(workspace: dict):
    install_codex(workspace)

    start_json(workspace, "--prompt", "check placement", "--model", "gpt-5.4-mini", "--effort", "high")

    argv = codex_argv(workspace)
    assert argv.index("-m gpt-5.4-mini") < argv.index("exec")
    assert argv.index('model_reasoning_effort="high"') < argv.index("exec")
    assert argv.endswith("-")


def test_resume_last_reuses_the_recorded_thread(workspace: dict):
    install_codex(workspace)
    start_json(workspace, "--prompt", "first pass")

    envelope = start_json(workspace, "--prompt", "keep going", "--resume-last")

    assert envelope["kind"] == "resume"
    assert envelope["resume_thread_id"] == "thread-fixture"
    assert "exec resume thread-fixture" in codex_argv(workspace)


def test_resume_last_without_history_fails_clearly(workspace: dict):
    install_codex(workspace)

    result = run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "x", "--resume-last")

    assert result.returncode == 1
    assert "no previous Codex thread recorded" in result.stderr


def test_review_targets_are_forwarded_and_stay_read_only(workspace: dict):
    install_codex(workspace)

    result = run(workspace, "review", "--workdir", workspace["repo"], "--base", "main", "--json")
    envelope = json.loads(result.stdout)

    assert envelope["kind"] == "review"
    assert envelope["sandbox"] == "read-only"
    argv = codex_argv(workspace)
    assert "exec review" in argv
    assert "--base main" in argv
    assert not argv.endswith(" -")


def test_failed_codex_run_maps_to_exit_code_two(workspace: dict):
    install_codex(workspace)
    workspace["env"]["FAKE_CODEX_EXIT"] = "1"

    result = run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "fail", "--json")
    envelope = json.loads(result.stdout)

    assert result.returncode == 2
    assert envelope["status"] == "failed"
    assert envelope["codex_exit_code"] == 1


def test_non_git_workdir_is_refused_before_launching_codex(workspace: dict):
    install_codex(workspace)
    scratch = workspace["tmp"] / "scratch"
    scratch.mkdir()

    result = run(workspace, "start", "--workdir", scratch, "--prompt", "x")

    assert result.returncode == 1
    assert "is not inside a Git repository" in result.stderr
    assert not Path(workspace["env"]["FAKE_CODEX_ARGV"]).exists()


def test_empty_prompt_is_refused(workspace: dict):
    install_codex(workspace)

    result = run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "   ")

    assert result.returncode == 1
    assert "prompt is empty" in result.stderr


def test_timeout_terminates_codex_and_reports_124(workspace: dict):
    install_codex(workspace, SLOW_CODEX)

    result = run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "slow", "--timeout", "2", "--json")
    envelope = json.loads(result.stdout)

    assert result.returncode == 124
    assert envelope["status"] == "timeout"
    assert envelope["thread_id"] == "slow-thread"


def test_background_job_can_be_cancelled(workspace: dict):
    install_codex(workspace, SLOW_CODEX)

    launched = json.loads(
        run(workspace, "start", "--workdir", workspace["repo"], "--prompt", "slow", "--background", "--json").stdout
    )
    job_id = launched["job_id"]

    waited = run(workspace, "wait", job_id, "--timeout", "2", "--json")
    assert waited.returncode == 124
    assert json.loads(waited.stdout)["status"] == "running"

    cancelled = json.loads(run(workspace, "cancel", job_id, "--json").stdout)
    assert cancelled["status"] == "cancelled"

    result = run(workspace, "result", job_id, "--json")
    assert result.returncode == 143
    assert json.loads(result.stdout)["status"] == "cancelled"


def test_status_lists_jobs_and_logs_expose_stderr(workspace: dict):
    install_codex(workspace)
    envelope = start_json(workspace, "--prompt", "record me")

    listing = json.loads(run(workspace, "status", "--json").stdout)
    assert [job["job_id"] for job in listing["jobs"]] == [envelope["job_id"]]

    logs = run(workspace, "logs", envelope["job_id"])
    assert "fixture stderr line" in logs.stdout


def test_unknown_job_is_an_input_error(workspace: dict):
    install_codex(workspace)

    result = run(workspace, "result", "no-such-job")

    assert result.returncode == 1
    assert "E_INPUT: unknown job" in result.stderr


def test_structured_output_is_parsed_when_a_schema_is_supplied(workspace: dict):
    schema = workspace["tmp"] / "schema.json"
    schema.write_text('{"type": "object"}', encoding="utf-8")
    body = FAKE_CODEX.replace("FIXTURE DONE", '{\\"verdict\\": \\"ok\\"}')
    install_codex(workspace, body)

    envelope = start_json(workspace, "--prompt", "structured", "--output-schema", schema)

    assert envelope["structured_output"] == {"verdict": "ok"}
    assert f"--output-schema {schema}" in codex_argv(workspace)
