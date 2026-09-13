import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/coding-agent/scripts/codex_run.py"
GOAL = ROOT / "skills/coordinator/scripts/coordinator_goal.py"


@pytest.fixture
def host(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    agy = binary / "agy"
    agy.write_text('''#!/usr/bin/env python3
import json, os, sys, time
if "--help" in sys.argv:
    print("--input-format --output-format --json-schema --sandbox")
    sys.exit(0)
if os.environ.get("AGY_NO_READ"):
    time.sleep(60)
prompt = sys.stdin.read()
json.loads(prompt)
print(json.dumps({"event":"init", "conversation_id":"conversation-fixture"}), flush=True)
if os.environ.get("AGY_SLOW"):
    time.sleep(60)
print(json.dumps({"event":"step_update", "step_type":"agent_response", "text_delta":"working"}))
if not os.environ.get("AGY_PARTIAL"):
    print(json.dumps({"event":"result", "status":"SUCCESS", "conversation_id":"conversation-fixture",
        "structured_output":{"status":"completed", "candidate_revision":"uncommitted-working-tree",
        "changed_files":[], "commands":[], "unresolved":[], "summary":"fixture"}}))
''')
    agy.chmod(0o755)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object"}')
    env = {"PATH": f"{binary}:{os.environ['PATH']}",
           "COORDINATOR_STATE_DIR": str(tmp_path / "private")}
    return tmp_path, repo, schema, env


def launch(host, *extra, env=None):
    tmp, repo, schema, default_env = host
    return subprocess.run([sys.executable, str(RUNNER), "start", "--agent", "agy", "--write",
        "--workdir", str(repo), "--prompt", "implement fixture", "--output-schema", str(schema),
        "--state-dir", str(tmp / "state"), "--json", *extra],
        capture_output=True, text=True, env=env or default_env, timeout=15)


def test_native_result_and_identity(host):
    result = launch(host, "--job-id", "attempt-1")
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["thread_id"] == "conversation-fixture"
    assert envelope["job_id"] == "attempt-1"
    assert envelope["structured_output"]["status"] == "completed"
    assert envelope["activity"]["text_updates"] == 1
    assert envelope["activity"]["tool_updates"] == 0
    assert launch(host, "--job-id", "attempt-1").returncode != 0


def test_soft_timeout_is_not_success(host):
    result = launch(host, env={**host[3], "AGY_PARTIAL": "1"})
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "failed"


def test_hard_execution_timeout(host):
    result = launch(host, "--timeout", "1", env={**host[3], "AGY_SLOW": "1"})
    assert result.returncode == 124
    assert json.loads(result.stdout)["status"] == "timeout"


def test_timeout_includes_blocked_prompt_delivery(host):
    prompt = host[0] / "large-prompt.txt"
    prompt.write_text("x" * 1048576)
    result = launch(host, "--prompt-file", str(prompt), "--timeout", "1",
                    env={**host[3], "AGY_NO_READ": "1"})
    assert result.returncode == 124


def test_unknown_attempt_retains_identity_and_refuses_retry(host):
    tmp, repo, _, env = host
    def goal(*args):
        return subprocess.run([sys.executable, str(GOAL), *args, "--workdir", str(repo),
            "--goal-id", "unknown", "--json"], capture_output=True, text=True, env=env, timeout=10)
    assert goal("init", "--objective", "fixture").returncode == 0
    contract = tmp / "contract.md"
    contract.write_text("Fixture")
    assert goal("freeze", "--role", "implementer", "--round", "r", "--contract", str(contract)).returncode == 0
    transport = tmp / "transport/scripts"
    transport.mkdir(parents=True)
    (transport / "coding-agent-run").write_text("unused")
    (transport / "codex_run.py").write_text("print('not a transport envelope')")
    dispatched = goal("dispatch", "--role", "implementer", "--round", "r", "--agent", "agy",
                      "--transport-dir", str(transport.parent))
    assert dispatched.returncode != 0
    stored = json.loads((repo / ".coordinator/unknown/goal.json").read_text())
    assert stored["state"] == "implementing"
    assert stored["jobs"][0]["session_id"].startswith("agy-")
    assert stored["jobs"][0]["transport_status"] == "unknown"
    assert goal("retry", "--role", "implementer", "--round", "r", "--note", "fixture").returncode != 0
    assert goal("collect", "--role", "implementer", "--round", "r").returncode != 0


def test_background_wait_and_cancel_do_not_start_new_turn(host):
    result = launch(host, "--background", "--job-id", "cancel-attempt", "--timeout", "30",
                    env={**host[3], "AGY_SLOW": "1"})
    assert result.returncode == 0, result.stderr
    tmp = host[0]
    def inspect(command, *extra):
        return subprocess.run([sys.executable, str(RUNNER), command, "cancel-attempt",
            "--state-dir", str(tmp / "state"), "--json", *extra],
            capture_output=True, text=True, env=host[3], timeout=10)
    try:
        for _ in range(100):
            snapshot = json.loads(inspect("status").stdout)
            if snapshot.get("thread_id"):
                break
            time.sleep(0.02)
        assert snapshot["thread_id"] == "conversation-fixture"
        assert inspect("wait", "--timeout", "1").returncode == 124
        assert json.loads(inspect("status").stdout)["status"] == "running"
        resumed = launch(host, "--resume", "conversation-fixture")
        assert resumed.returncode != 0
    finally:
        cancelled = inspect("cancel")
    assert cancelled.returncode == 0, cancelled.stderr
    assert json.loads(cancelled.stdout)["status"] == "cancelled"
    for _ in range(100):
        try:
            os.kill(snapshot["child_pid"], 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail("cancelled job's provider process is still alive")


def test_coordinator_native_dispatch_and_collect(host):
    tmp, repo, _, env = host
    def goal(*args):
        result = subprocess.run([sys.executable, str(GOAL), *args, "--workdir", str(repo), "--json"],
                                capture_output=True, text=True, env=env, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    goal("init", "--goal-id", "fixture", "--objective", "offline fixture")
    contract = tmp / "contract.md"
    contract.write_text("Implement a fixture. No external writes.")
    goal("freeze", "--goal-id", "fixture", "--round", "round-1", "--role", "implementer", "--contract", str(contract))
    dispatched = goal("dispatch", "--goal-id", "fixture", "--round", "round-1", "--role", "implementer", "--agent", "agy")
    assert dispatched["job"]["transport_status"] == "completed"
    goal("status", "--goal-id", "fixture")
    collected = goal("collect", "--goal-id", "fixture", "--round", "round-1", "--role", "implementer")
    assert collected["outcome"] == "collected"


def test_nested_payload_validation():
    spec = importlib.util.spec_from_file_location("goal", GOAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = {key: [] for key in module.REVIEWER_REQUIRED}
    payload.update(schema_version=1, role="reviewer", verdict="go", round_id="r",
                   candidate_revision="candidate", checks=["not an object"])
    assert "checks entries must be objects" in module.validate_envelope("reviewer", payload)


def test_lost_worker_cannot_be_marked_safely_cancelled(host):
    spec = importlib.util.spec_from_file_location("runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = module.resolve_state_dir(str(host[0] / "state"))
    job_dir = module.create_job(state, "start", host[1], "fixture", {
        "agent": "agy", "job_id": "lost-attempt", "sandbox": "workspace-write"})
    job = module.read_job(job_dir)
    job.update(status="running", pid=999999999)
    module.write_json(job_dir / "job.json", job)
    result = subprocess.run([sys.executable, str(RUNNER), "cancel", "lost-attempt",
        "--state-dir", str(state), "--json"], capture_output=True, text=True, env=host[3])
    assert result.returncode != 0
    assert module.read_job(job_dir)["status"] == "running"
