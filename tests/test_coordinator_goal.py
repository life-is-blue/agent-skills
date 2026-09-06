import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "coordinator" / "scripts" / "coordinator_goal.py"

FAKE_TRANSPORT = r"""#!/usr/bin/env bash
set -u
cmd="$1"; shift
[ "$cmd" = "run" ] || exit 64
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) A="$2"; shift 2;;
    --workdir) W="$2"; shift 2;;
    --prompt-file) shift 2;;
    --result-file) R="$2"; shift 2;;
    --json) shift;;
    *) shift;;
  esac
done
if [ -n "${FAKE_ARTIFACT_FILE:-}" ]; then
  mkdir -p "$W/$(dirname "$R")"
  cat "$FAKE_ARTIFACT_FILE" > "$W/$R"
fi
printf '{"schema_version":1,"session_id":"fake-1","status":"completed","agent":"%s","worker_exit_code":0,"result_artifact":{"status":"present","path":"%s/%s"},"errors":[]}\n' "$A" "$W" "$R"
"""

IMPL_OK = {
    "schema_version": 1,
    "role": "implementer",
    "status": "completed",
    "round_id": "round-1",
    "start_revision": "a",
    "candidate_revision": "b",
    "changed_files": ["src/x.py"],
    "commands": [{"command": "pytest -q", "exit_code": 0}],
    "unresolved": [],
    "summary": "done",
}

REVIEW_GO = {
    "schema_version": 1,
    "role": "reviewer",
    "verdict": "go",
    "round_id": "round-1",
    "start_revision": "a",
    "candidate_revision": "b",
    "checks": [
        {"id": "open-1", "kind": "open", "required": True, "passed": True,
         "evidence": "pytest -q -> 0"}
    ],
    "blockers": [],
    "spec_uncertainties": [],
    "infrastructure_errors": [],
}

REVIEW_NO_GO = {
    **REVIEW_GO,
    "verdict": "no-go",
    "checks": [
        {"id": "withheld-1", "kind": "withheld", "required": True,
         "passed": False, "evidence_ref": "private:round-1/c1"}
    ],
    "blockers": [{"check_id": "withheld-1", "summary": "dropped value",
                  "declassified": True}],
}


def make_transport(tmp_path: Path) -> Path:
    transport = tmp_path / "fake-transport"
    script = transport / "scripts" / "coding-agent-run"
    script.parent.mkdir(parents=True)
    script.write_text(FAKE_TRANSPORT, encoding="utf-8")
    script.chmod(0o755)
    return transport


def run_goal(*args: object, artifact: dict | None = None,
                    raw_artifact: str | None = None,
                    check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if artifact is not None or raw_artifact is not None:
        holder = Path(os.environ["TMPDIR"] if "TMPDIR" in os.environ else "/tmp")
        payload = raw_artifact if raw_artifact is not None else json.dumps(artifact)
        artifact_file = holder / f"fake-artifact-{os.getpid()}.json"
        artifact_file.write_text(payload, encoding="utf-8")
        env["FAKE_ARTIFACT_FILE"] = str(artifact_file)
    else:
        env.pop("FAKE_ARTIFACT_FILE", None)
    proc = subprocess.run(
        [sys.executable, str(RUNNER), *(str(a) for a in args), "--json"],
        text=True,
        capture_output=True,
        env=env,
    )
    if check:
        assert proc.returncode == 0, proc.stderr
    return proc


def payload(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


def init_run(tmp_path: Path, repair_bound: int = 1) -> None:
    run_goal(
        "init", "--workdir", tmp_path, "--goal-id", "r1",
        "--objective", "fixture objective", "--repair-bound", repair_bound,
    )


def freeze_round(tmp_path: Path, transport: Path, role: str = "implementer",
                 name: str = "contract.md") -> Path:
    contract = tmp_path / name
    contract.write_text("# frozen contract\n", encoding="utf-8")
    run_goal(
        "freeze", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", role, "--contract", contract,
    )
    return contract


def dispatch_and_collect(tmp_path: Path, transport: Path, role: str,
                         artifact: dict | None) -> dict:
    dispatch = run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", role,
        "--transport-dir", transport, artifact=artifact,
    )
    collected = run_goal(
        "collect", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", role,
    )
    return payload(collected)


def test_init_creates_run_directory(tmp_path: Path):
    init_run(tmp_path)
    run_dir = tmp_path / ".coordinator" / "r1"
    assert (run_dir / "goal.json").is_file()
    assert (run_dir / "ledger.json").is_file()
    assert (run_dir / "constraints.md").is_file()
    state = json.loads((run_dir / "goal.json").read_text())
    assert state["state"] == "establishing"
    assert state["repair_bound"] == 1


def test_freeze_moves_establishing_to_ready(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    status = payload(run_goal("status", "--workdir", tmp_path,
                                     "--goal-id", "r1"))
    assert status["state"] == "ready"
    refreeze = run_goal(
        "freeze", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--contract", tmp_path / "contract.md",
        check=False,
    )
    assert refreeze.returncode == 2
    assert "guard:" in refreeze.stderr


def test_dispatch_guard_requires_ready(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    proc = run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--transport-dir", transport, check=False,
    )
    assert proc.returncode == 2
    assert "cannot dispatch an implementer" in proc.stderr


def test_full_cycle_reaches_completed(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")

    delivery = dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    assert delivery["outcome"] == "collected"
    assert delivery["status"] == "completed"

    review = dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_GO)
    assert review["outcome"] == "collected"
    assert review["mechanical_go"] is True

    advanced = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1",
        "--to", "completed", "--note", "gate reproduced",
    ))
    assert advanced["state"] == "completed"
    again = run_goal("advance", "--workdir", tmp_path, "--goal-id", "r1",
                            "--to", "ready", check=False)
    assert again.returncode == 2


def test_missing_artifact_is_infrastructure_failure(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--transport-dir", transport,
    )
    collected = payload(run_goal(
        "collect", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
    ))
    assert collected["outcome"] == "infrastructure-failure"
    assert collected["state"] == "implementing"


def test_malformed_envelope_is_infrastructure_failure(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    collected = dispatch_and_collect(tmp_path, transport, "implementer",
                                     artifact=None)
    assert collected["outcome"] == "infrastructure-failure"

    run_dir = tmp_path / ".coordinator" / "r1"
    (run_dir / "deliveries" / "round-1.json").write_text(
        json.dumps({"role": "implementer", "status": "completed"}),
        encoding="utf-8",
    )
    recollected = payload(run_goal(
        "collect", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
    ))
    assert recollected["outcome"] == "infrastructure-failure"
    assert "missing fields" in recollected["errors"][0]


def test_no_go_repair_then_bound_forces_blocked(tmp_path: Path):
    init_run(tmp_path, repair_bound=1)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    review = dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_NO_GO)
    assert review["mechanical_go"] is False

    repairing = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "repairing",
    ))
    assert repairing["state"] == "repairing"
    assert repairing["repairs_used"] == 1

    freeze_round(tmp_path, transport, name="contract2.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_NO_GO)
    exhausted = run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1",
        "--to", "repairing", check=False,
    )
    assert exhausted.returncode == 2
    assert "repair bound 1 exhausted" in exhausted.stderr

    blocked = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "blocked",
    ))
    assert blocked["state"] == "blocked"


def test_completed_requires_mechanical_go(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_NO_GO)
    proc = run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1",
        "--to", "completed", check=False,
    )
    assert proc.returncode == 2
    assert "mechanical go" in proc.stderr


def test_archive_copies_receipt_bundle_to_skill_runs(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_GO)
    run_goal("advance", "--workdir", tmp_path, "--goal-id", "r1",
                    "--to", "completed")

    archived = payload(run_goal("archive", "--workdir", tmp_path,
                                       "--goal-id", "r1"))
    sink = Path(archived["archived_to"])
    assert sink.parent == (ROOT / "skills" / "coordinator" / "goals")
    assert (sink / "goal.json").is_file()
    assert (sink / "ledger.json").is_file()
    assert (sink / "contracts" / "round-1.md").is_file()
    assert (sink / "deliveries" / "round-1.json").is_file()
    assert (sink / "reviews" / "round-1.json").is_file()
    meta = json.loads((sink / "archive-meta.json").read_text())
    assert meta["state_at_archive"] == "completed"

    repeat = run_goal("archive", "--workdir", tmp_path, "--goal-id", "r1",
                             check=False)
    assert repeat.returncode != 0
    forced = run_goal("archive", "--workdir", tmp_path, "--goal-id", "r1",
                             "--force")
    assert payload(forced)["state"] == "completed"
    import shutil
    shutil.rmtree(sink)


def test_human_gate_parks_and_resumes(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    parked = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1",
        "--to", "human-gate", "--note", "need scope decision",
    ))
    assert parked["state"] == "human-gate"
    state = json.loads(
        (tmp_path / ".coordinator" / "r1" / "goal.json").read_text()
    )
    assert state["resume_state"] == "ready"
    resumed = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "ready",
    ))
    assert resumed["state"] == "ready"


def test_retry_implementer_preserves_repair_budget(tmp_path: Path):
    init_run(tmp_path)  # repair_bound = 1
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)

    # Malformed envelope: collect records an infrastructure failure and the
    # artifact stays in place (the transport would refuse to overwrite it).
    dispatch = run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--transport-dir", transport, raw_artifact='{"status": "complete"}',
    )
    assert payload(dispatch)["state"] == "implementing"
    collected = run_goal(
        "collect", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
    )
    assert payload(collected)["outcome"] == "infrastructure-failure"

    retried = payload(run_goal(
        "retry", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--note", "envelope status enum invalid",
    ))
    assert retried["state"] == "ready"
    assert retried["repairs_used"] == 0  # infra retry must not burn the bound
    assert retried["set_aside"] is not None

    goal_dir = tmp_path / ".coordinator" / "r1"
    assert not (goal_dir / "deliveries" / "round-1.json").exists()
    assert (goal_dir / retried["set_aside"]).is_file()
    ledger = json.loads((goal_dir / "ledger.json").read_text())
    retries = ledger["rounds"]["round-1"]["infra_retries"]
    assert retries[0]["note"] == "envelope status enum invalid"

    # The reopened round can be redispatched and collected normally.
    delivery = dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    assert delivery["outcome"] == "collected"
    assert delivery["status"] == "completed"


def test_retry_reviewer_returns_to_implementing(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)

    run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
        "--transport-dir", transport, raw_artifact='{"verdict": "yes"}',
    )
    collected = run_goal(
        "collect", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
    )
    assert payload(collected)["outcome"] == "infrastructure-failure"

    retried = payload(run_goal(
        "retry", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
        "--note", "verdict envelope malformed",
    ))
    # reviewer dispatches from implementing, so retry resumes there
    assert retried["state"] == "implementing"
    review = dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_GO)
    assert review["mechanical_go"] is True


def test_retry_guard_rejects_idle_states(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    proc = run_goal(
        "retry", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--note", "nothing in flight", check=False,
    )
    assert proc.returncode == 2
    assert "cannot retry" in proc.stderr
