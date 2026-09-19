import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "coordinator" / "scripts" / "coordinator_goal.py"

FAKE_TRANSPORT = r"""#!/usr/bin/env bash
set -u
cmd="$1"; shift
if [ "$cmd" = status ]; then
  cat "$0.$1.json"
  exit
fi
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
S="fake-$$"
printf '{"schema_version":1,"session_id":"%s","workdir":"%s","status":"completed","agent":"%s","worker_exit_code":0,"result_artifact":{"status":"present","path":"%s/%s"},"errors":[]}\n' "$S" "$W" "$A" "$W" "$R" > "$0.$S.json"
cat "$0.$S.json"
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


@pytest.mark.parametrize("observed", ["running", "stopping", "lost", "wrong-root", "missing",
                                      "missing-exit", "wait-timeout"])
def test_retry_uses_live_runner_state_not_cached_failure(tmp_path, observed):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    dispatched = payload(run_goal("dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer", "--transport-dir", transport,
        artifact=IMPL_OK))
    job = dispatched["job"]
    receipt_file = Path(job["transport_runner"] + "." + job["session_id"] + ".json")
    receipt = json.loads(receipt_file.read_text())
    if observed == "wrong-root":
        receipt["workdir"] = str(tmp_path.parent)
    elif observed == "missing-exit":
        receipt["worker_exit_code"] = None
    elif observed == "wait-timeout":
        receipt["wait_timed_out"] = True
    else:
        receipt["status"] = observed
    receipt_file.write_text("not-json" if observed == "missing" else json.dumps(receipt))
    goal_file = tmp_path / ".coordinator/r1/goal.json"
    state = json.loads(goal_file.read_text())
    state["jobs"][0]["transport_status"] = "failed"
    goal_file.write_text(json.dumps(state))
    result = run_goal("retry", "--workdir", tmp_path, "--goal-id", "r1", "--round", "round-1",
        "--role", "implementer", "--note", "log looked broken", check=False)
    assert result.returncode != 0
    assert "active or unknown" in result.stderr
    assert (tmp_path / ".coordinator/r1/deliveries/round-1.json").exists()
    assert json.loads(goal_file.read_text())["state"] == "implementing"


def run_goal(*args: object, artifact: dict | None = None,
                    raw_artifact: str | None = None,
                    state_dir: Path | None = None,
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
    if state_dir is None:
        values = [str(arg) for arg in args]
        workdir = Path(values[values.index("--workdir") + 1]).resolve()
        state_dir = workdir.parent / f".{workdir.name}-coordinator-state"
    env["COORDINATOR_STATE_DIR"] = str(state_dir)
    values = [str(arg) for arg in args]
    workdir = Path(values[values.index("--workdir") + 1]).resolve()
    bin_dir = workdir / "fake-help-bin"
    bin_dir.mkdir(exist_ok=True)
    for agent in ("codex", "claude"):
        binary = bin_dir / agent
        binary.write_text('#!/bin/sh\necho "--model --effort"\n')
        binary.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
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
    runtime = tmp_path / ".coordinator"
    runtime.mkdir(exist_ok=True)
    (runtime / "config.json").write_text(json.dumps({"schema_version": 1,
        "implementer": [{"agent": "codex", "model": "fixture", "effort": "high"}],
        "reviewer": [{"agent": "claude", "model": "fixture-review"}]}))
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


def test_review_environment_failure_is_not_candidate_rejection(tmp_path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    freeze_round(tmp_path, transport, role="reviewer")
    review = {**REVIEW_NO_GO, "infrastructure_errors": ["loopback bind EPERM"]}
    result = dispatch_and_collect(tmp_path, transport, "reviewer", review)
    assert result["outcome"] == "infrastructure-failure"
    assert result["mechanical_go"] is False
    retry = payload(run_goal("retry", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer", "--note", "declare authorized loopback evidence path"))
    assert retry["repairs_used"] == 0


@pytest.mark.parametrize("other_provider,override,actual_model,expected", [
    (False, None, "fixture", "codex"),
    (True, None, "fixture", "claude"),
    (False, "fixture", "fixture", None),
    (False, "fixture", "alternate-executor", "codex"),
    (False, None, None, None),
])
def test_review_pair_selection_uses_actual_model(tmp_path, other_provider, override, actual_model, expected):
    init_run(tmp_path)
    config_path = tmp_path / ".coordinator/config.json"
    config = json.loads(config_path.read_text())
    config["reviewer"] = [{"agent": "codex", "model": "gpt-5.6-sol", "effort": "high"}]
    if other_provider:
        config["reviewer"].append({"agent": "claude", "model": "fixture-review"})
    config_path.write_text(json.dumps(config))
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    # Also exercise historical jobs and execution settings differing from config.
    goal_path = tmp_path / ".coordinator/r1/goal.json"
    state = json.loads(goal_path.read_text())
    if actual_model is None:
        state["jobs"][-1].pop("model")
    else:
        state["jobs"][-1]["model"] = actual_model
    goal_path.write_text(json.dumps(state))
    extra = ["--model", override] if override else []
    result = run_goal("dispatch", "--workdir", tmp_path, "--goal-id", "r1",
                      "--round", "round-1", "--role", "reviewer",
                      "--transport-dir", transport, *extra, artifact=REVIEW_GO, check=False)
    if expected is None:
        assert result.returncode != 0
        assert "distinct provider/model" in result.stderr
        state = json.loads((tmp_path / ".coordinator/r1/goal.json").read_text())
        assert len(state["jobs"]) == 1
    else:
        assert result.returncode == 0, result.stderr
        job = payload(result)["job"]
        assert job["agent"] == expected
        if expected == "codex":
            assert (job["model"], job["effort"]) == (override or "gpt-5.6-sol", "high")


def test_implementation_override_cannot_remove_review_option(tmp_path):
    init_run(tmp_path)
    config_path = tmp_path / ".coordinator/config.json"
    config = json.loads(config_path.read_text())
    config["reviewer"] = [{"agent": "codex", "model": "gpt-5.6-sol"}]
    config_path.write_text(json.dumps(config))
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    result = run_goal("dispatch", "--workdir", tmp_path, "--goal-id", "r1",
                      "--round", "round-1", "--role", "implementer",
                      "--model", "gpt-5.6-sol", "--transport-dir", transport, check=False)
    assert result.returncode != 0
    assert "distinct provider/model" in result.stderr
    assert not json.loads((tmp_path / ".coordinator/r1/goal.json").read_text()).get("jobs")


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


def test_ready_freezes_only_a_new_round_after_review(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)

    def freeze(round_id: str):
        return run_goal(
            "freeze", "--workdir", tmp_path, "--goal-id", "r1",
            "--round", round_id, "--contract", tmp_path / "contract.md",
            check=False,
        )

    skipped = freeze("round-2")
    assert skipped.returncode == 2
    assert "round round-1 has no collected review" in skipped.stderr

    freeze_round(tmp_path, transport, role="reviewer", name="review.md")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    dispatch_and_collect(tmp_path, transport, "reviewer", REVIEW_GO)
    run_goal("advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "ready")

    refrozen = freeze("round-1")
    assert refrozen.returncode == 2
    assert "already has a frozen contract" in refrozen.stderr

    nxt = freeze("round-2")
    assert payload(nxt)["state"] == "ready"
    status = payload(run_goal("status", "--workdir", tmp_path, "--goal-id", "r1"))
    assert status["current_round"] == "round-2"


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


def test_reviewer_contract_is_private_and_dispatches(tmp_path: Path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    state_dir = tmp_path / "host-state"
    init_run(worktree)
    transport = make_transport(worktree)
    freeze_round(worktree, transport)
    secret = "WITHHELD-CANARY-9f4d2a"
    review_contract = tmp_path / "review-contract.md"
    review_contract.write_text(secret, encoding="utf-8")
    run_goal(
        "freeze", "--workdir", worktree, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
        "--contract", review_contract, state_dir=state_dir,
    )

    assert secret not in "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in worktree.rglob("*") if path.is_file()
    )
    ledger = json.loads(
        (worktree / ".coordinator" / "r1" / "ledger.json").read_text()
    )
    assert ledger["rounds"]["round-1"]["review_contract"] == {
        "private": True,
        "sha256": hashlib.sha256(secret.encode()).hexdigest(),
    }

    dispatch_and_collect(worktree, transport, "implementer", IMPL_OK)
    run_goal(
        "dispatch", "--workdir", worktree, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
        "--transport-dir", transport, artifact=REVIEW_GO, state_dir=state_dir,
    )
    prompt = state_dir / "r1" / "contracts" / "round-1-review.prompt.md"
    assert secret in prompt.read_text()
    assert not (worktree / ".coordinator" / "r1" / "contracts"
                / "round-1-review.prompt.md").exists()


def test_reviewer_dispatch_falls_back_to_legacy_goal_contract(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    legacy = tmp_path / ".coordinator" / "r1" / "contracts" / "round-1-review.md"
    legacy.write_text("legacy withheld contract", encoding="utf-8")
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)
    state_dir = tmp_path.parent / f"{tmp_path.name}-private"
    run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "reviewer",
        "--transport-dir", transport, artifact=REVIEW_GO, state_dir=state_dir,
    )
    prompt = state_dir / "r1" / "contracts" / "round-1-review.prompt.md"
    assert "legacy withheld contract" in prompt.read_text()


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


def test_archive_copies_receipt_bundle_to_worktree(tmp_path: Path):
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
    assert sink.parent == (tmp_path / ".coordinator" / "archives")
    assert (sink / "goal.json").is_file()
    assert (sink / "ledger.json").is_file()
    assert (sink / "contracts" / "round-1.md").is_file()
    assert (sink / "contracts" / "round-1-review.md").is_file()
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


def test_generated_runtime_ignore_preserves_root_policy(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    root_ignore = tmp_path / ".gitignore"
    root_ignore.write_text("existing-policy\n")
    runtime = tmp_path / ".coordinator"
    runtime.mkdir()
    nested_ignore = runtime / ".gitignore"
    nested_ignore.write_text("# user policy\n!keep.json\n")
    init_run(tmp_path)
    assert root_ignore.read_text() == "existing-policy\n"
    assert nested_ignore.read_text() == "# user policy\n!keep.json\n*\n"
    for relative in (".coordinator/r1/goal.json", ".coordinator/.gitignore"):
        ignored = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", relative],
                                 capture_output=True, text=True)
        assert ignored.returncode == 0, ignored.stderr
    before = nested_ignore.read_bytes()
    run_goal("init", "--workdir", tmp_path, "--goal-id", "r2", "--objective", "second")
    assert nested_ignore.read_bytes() == before


def test_runtime_ignore_does_not_untrack_existing_files(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    runtime = tmp_path / ".coordinator"
    runtime.mkdir()
    tracked = runtime / "existing.txt"
    tracked.write_text("already tracked\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".coordinator/existing.txt"], check=True)
    index = subprocess.run(["git", "-C", str(tmp_path), "ls-files", "--stage"],
                           check=True, capture_output=True, text=True).stdout
    init_run(tmp_path)
    after = subprocess.run(["git", "-C", str(tmp_path), "ls-files", "--stage"],
                           check=True, capture_output=True, text=True).stdout
    assert after == index


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


def test_dispatch_injects_envelope_tail(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    run_goal(
        "dispatch", "--workdir", tmp_path, "--goal-id", "r1",
        "--round", "round-1", "--role", "implementer",
        "--transport-dir", transport, artifact=IMPL_OK,
    )
    prompt = (tmp_path / ".coordinator" / "r1" / "contracts"
              / "round-1.prompt.md").read_text()
    assert "# frozen contract" in prompt          # contract text preserved
    assert "机械校验" in prompt                     # tail injected
    assert "runner 自动补齐" in prompt              # registry fields disclaimed
    assert "deliveries/round-1.json" in prompt      # exact result path stated
    assert prompt.rindex("机械校验") > prompt.rindex("frozen contract")  # tail is last


def test_blocked_resumes_via_human_gate_only(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    dispatch_and_collect(tmp_path, transport, "implementer", IMPL_OK)

    parked = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "blocked",
        "--note", "bound exhausted pending user decision"))
    assert parked["state"] == "blocked"

    # blocked is holding, not death: human-gate resumes it
    resumed = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "human-gate",
        "--note", "user decided"))
    assert resumed["state"] == "human-gate"
    back = payload(run_goal(
        "advance", "--workdir", tmp_path, "--goal-id", "r1", "--to", "ready"))
    assert back["state"] == "ready"

    # but blocked cannot skip the human gate (re-park, then try the direct jump)
    run_goal("advance", "--workdir", tmp_path, "--goal-id", "r1",
             "--to", "blocked", "--note", "again")
    illegal = run_goal("advance", "--workdir", tmp_path, "--goal-id", "r1",
                       "--to", "ready", check=False)
    assert illegal.returncode == 2
    assert "not legal" in illegal.stderr


def test_collect_autofills_runner_known_fields(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    # worker-authored fields only; registry fields are the runner's job
    lean = {k: v for k, v in IMPL_OK.items()
            if k not in ("schema_version", "role", "round_id", "start_revision")}
    delivery = dispatch_and_collect(tmp_path, transport, "implementer", lean)
    assert delivery["outcome"] == "collected"
    assert set(delivery["autofilled"]) == {
        "schema_version", "role", "round_id", "start_revision"}
    assert delivery["status"] == "completed"


def test_collect_rejects_inconsistent_runner_fields(tmp_path: Path):
    init_run(tmp_path)
    transport = make_transport(tmp_path)
    freeze_round(tmp_path, transport)
    wrong = {**IMPL_OK, "round_id": "round-9"}
    delivery = dispatch_and_collect(tmp_path, transport, "implementer", wrong)
    assert delivery["outcome"] == "infrastructure-failure"
    assert "round_id" in delivery["detail"]
