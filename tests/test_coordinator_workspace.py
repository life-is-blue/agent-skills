import json
import fcntl
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/coordinator/scripts/coordinator_goal.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


@pytest.fixture
def host(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "source.bin").write_bytes(b"baseline\x00\xff")
    (repo / ".gitignore").write_text(".env\n")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "fixture")
    binary = tmp_path / "bin"
    binary.mkdir()
    for agent in ("codex", "claude"):
        cli = binary / agent
        cli.write_text('#!/bin/sh\necho "--model --effort"\n')
        cli.chmod(0o755)
    env = {"PATH": f"{binary}:/usr/bin:/bin", "HOME": str(tmp_path),
           "COORDINATOR_STATE_DIR": str(tmp_path / "private")}
    runtime = repo / ".coordinator"
    runtime.mkdir()
    (runtime / "config.json").write_text(json.dumps({"schema_version": 1,
        "implementer": [{"agent": "codex", "model": "gpt-5.6-luna", "effort": "high"}],
        "reviewer": [{"agent": "codex", "model": "gpt-5.6-sol", "effort": "medium"}]}))
    transport = tmp_path / "transport/scripts"
    transport.mkdir(parents=True)
    implementation = transport / "transport.py"
    implementation.write_text('''import json, pathlib, sys, uuid
args = sys.argv[1:]
if args[0] == "status":
    print((pathlib.Path(__file__).parent / (args[1] + ".json")).read_text())
    sys.exit(0)
def flag(name): return args[args.index(name) + 1]
workdir = pathlib.Path(flag("--workdir"))
result = workdir / flag("--result-file")
result.parent.mkdir(parents=True, exist_ok=True)
result.write_text(json.dumps({"status":"completed", "candidate_revision":"uncommitted-working-tree",
    "changed_files":[], "commands":[], "unresolved":[], "summary":"fixture"}))
receipt = {"status":"completed", "agent":flag("--agent"), "session_id":uuid.uuid4().hex,
    "workdir":str(workdir), "worker_exit_code":0, "result_artifact":{"status":"present", "path":str(result)}}
(pathlib.Path(__file__).parent / (receipt["session_id"] + ".json")).write_text(json.dumps(receipt))
print(json.dumps(receipt))
''')
    (transport / "coding-agent-run").write_text(f"exec {shlex.quote(sys.executable)} {shlex.quote(str(implementation))} \"$@\"\n")
    return repo, env, transport.parent


def run(host, *args, ok=True):
    repo, env, _ = host
    proc = subprocess.run([sys.executable, str(SCRIPT), *args, "--workdir", str(repo),
                           "--goal-id", "g", "--json"], capture_output=True, text=True, env=env, timeout=15)
    if ok:
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)
    return proc


def init(host):
    run(host, "init", "--objective", "fixture")


def prepare(host):
    init(host)
    return Path(run(host, "workspace", "prepare")["workspace"]["path"])


def collected_candidate(host):
    path = prepare(host)
    repo, _, transport = host
    contract = repo / ".coordinator/contract.md"
    contract.write_text("Fixture")
    for role in ("implementer", "reviewer"):
        run(host, "freeze", "--round", "r", "--role", role, "--contract", str(contract))
    dispatched = run(host, "dispatch", "--round", "r", "--role", "implementer", "--transport-dir", str(transport))
    assert dispatched["job"]["workdir"] == str(path)
    assert (path / ".coordinator/g/ledger.json").is_file()
    assert (path / ".coordinator/g/constraints.md").is_file()
    assert (path / ".coordinator/g/contracts/r.md").is_file()
    assert not (path / ".coordinator/g/contracts/r-review.md").exists()
    assert run(host, "collect", "--round", "r", "--role", "implementer")["outcome"] == "collected"
    return path


def test_primary_checkout_cannot_dispatch(host):
    init(host)
    result = run(host, "dispatch", "--round", "r", "--role", "implementer", ok=False)
    assert result.returncode != 0
    assert "control checkout" in result.stderr
    assert not json.loads((host[0] / ".coordinator/g/goal.json").read_text())["jobs"]


def test_plain_runner_status_roundtrip_uses_recorded_state_root(host):
    source = prepare(host)
    repo, env, _ = host
    env["CODING_AGENT_STATE_DIR"] = str(repo / ".coordinator/transport")
    cli = Path(env["PATH"].split(":")[0]) / "codex"
    cli.write_text(f'''#!{sys.executable}
import json, pathlib, sys
if "--help" in sys.argv:
    print("--model --effort")
else:
    sys.stdin.read()
    result = pathlib.Path(".coordinator/g/deliveries/r.json")
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps({{"status":"completed", "candidate_revision":"uncommitted-working-tree",
        "changed_files":[], "commands":[], "unresolved":[], "summary":"offline fixture"}}))
''')
    contract = repo / ".coordinator/contract.md"
    contract.write_text("Offline fixture")
    run(host, "freeze", "--round", "r", "--contract", str(contract))
    job = run(host, "dispatch", "--round", "r", "--role", "implementer",
              "--transport-dir", str(ROOT / "skills/coding-agent"))["job"]
    assert job["workdir"] == str(source)
    # Changing current configuration must not redirect inspection of an old job.
    env["CODING_AGENT_STATE_DIR"] = str(repo / ".coordinator/not-the-original-store")
    inspected = run(host, "status")["jobs"][0]
    assert inspected["transport_status"] == "completed"
    assert inspected["activity"]["log_bytes"] is not None
    assert run(host, "collect", "--round", "r", "--role", "implementer")["outcome"] == "collected"


@pytest.mark.parametrize("choice", [None, False, True])
def test_dispatch_inherits_only_explicit_local_commit_consent(host, choice):
    config_path = host[0] / ".coordinator/config.json"
    config = json.loads(config_path.read_text())
    if choice is not None:
        config["execution"] = {"local_commits": choice}
    config_path.write_text(json.dumps(config))
    source = collected_candidate(host)
    goal = json.loads((host[0] / ".coordinator/g/goal.json").read_text())
    assert goal["jobs"][0]["local_commits"] is (choice is True)
    prompt = (host[0] / ".coordinator/g/contracts/r.prompt.md").read_text()
    assert ("Local milestone commits are authorized" in prompt) is (choice is True)
    run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r")
    reviewed = run(host, "dispatch", "--round", "r", "--role", "reviewer",
                   "--transport-dir", str(host[2]))
    assert reviewed["job"]["local_commits"] is False
    assert git(source, "rev-parse", "HEAD") == git(host[0], "rev-parse", "HEAD")


def test_review_snapshot_preserves_local_milestone_commit(host):
    source = collected_candidate(host)
    before = git(host[0], "rev-parse", "HEAD")
    (source / "source.bin").write_bytes(b"verified milestone")
    git(source, "add", "source.bin")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "milestone")
    reviewer = Path(run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r")["workspace"]["path"])
    assert git(source, "rev-parse", "HEAD") != before
    assert git(reviewer, "rev-parse", "HEAD") == git(source, "rev-parse", "HEAD")
    assert git(host[0], "rev-parse", "HEAD") == before
    assert (reviewer / "source.bin").read_bytes() == b"verified milestone"


def test_prepare_is_local_ignored_and_reuses_without_reset(host):
    repo = host[0]
    before_head = git(repo, "rev-parse", "HEAD")
    before_index = (repo / ".git/index").read_bytes()
    path = prepare(host)
    assert path == repo / ".coordinator/worktrees/g/implementer"
    (path / "source.bin").write_bytes(b"work in progress")
    assert run(host, "workspace", "prepare")["status"] == "reused"
    assert (path / "source.bin").read_bytes() == b"work in progress"
    assert git(repo, "rev-parse", "HEAD") == before_head
    assert (repo / ".git/index").read_bytes() == before_index
    assert git(repo, "check-ignore", str(path)).strip()
    assert run(host, "workspace", "status")["workspaces"]["implementer"]["valid"]


def test_freeze_preserves_binary_modes_and_explicit_new_files(host):
    source = collected_candidate(host)
    (source / "source.bin").write_bytes(b"candidate\x00\xfe")
    (source / "source.bin").chmod(0o755)
    (source / "new.py").write_text("print('candidate')\n")
    (source / "staged.py").write_text("# staged addition\n")
    git(source, "add", "staged.py")
    (source / ".env").write_text("fixture-only; must not be copied")
    index_path = Path(git(source, "rev-parse", "--absolute-git-dir").decode().strip()) / "index"
    before = index_path.read_bytes()
    denied = run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r", ok=False)
    assert "include-untracked" in denied.stderr
    result = run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r", "--include-untracked", "new.py")
    reviewer = Path(result["workspace"]["path"])
    assert (reviewer / "source.bin").read_bytes() == b"candidate\x00\xfe"
    assert (reviewer / "source.bin").stat().st_mode & 0o111
    assert (reviewer / "new.py").read_bytes() == (source / "new.py").read_bytes()
    assert (reviewer / "staged.py").is_file()
    assert not (reviewer / ".env").exists()
    assert index_path.read_bytes() == before
    assert git(source, "rev-parse", "HEAD") == git(reviewer, "rev-parse", "HEAD")
    assert result["config_path"] == str(host[0] / ".coordinator/config.json")


def test_freeze_keeps_tracked_files_under_ignore_rules(host):
    repo = host[0]
    (repo / "data").mkdir()
    (repo / "data/tracked.txt").write_text("baseline\n")
    git(repo, "add", "data/tracked.txt")
    (repo / ".gitignore").write_text(".env\ndata/\n")
    git(repo, "add", ".gitignore")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "tracked file later matched by an ignore rule")
    source = collected_candidate(host)
    (source / "data/tracked.txt").write_text("candidate\n")
    (source / "source.bin").unlink()
    reviewer = Path(run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r")["workspace"]["path"])
    assert (reviewer / "data/tracked.txt").read_text() == "candidate\n"
    assert not (reviewer / "source.bin").exists()


@pytest.mark.parametrize("change", ["candidate", "reviewer", "git-identity"])
def test_dispatch_rejects_changed_frozen_workspace(host, change):
    source = collected_candidate(host)
    reviewer = Path(run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r")["workspace"]["path"])
    if change == "git-identity":
        (reviewer / ".git").write_text(f"gitdir: {host[0] / '.git'}\n")
        assert not run(host, "workspace", "status")["workspaces"]["reviewer:r"]["valid"]
    else:
        target = source if change == "candidate" else reviewer
        (target / "source.bin").write_bytes(b"changed after freeze")
    result = run(host, "dispatch", "--round", "r", "--role", "reviewer", ok=False)
    assert result.returncode != 0
    state = json.loads((host[0] / ".coordinator/g/goal.json").read_text())
    assert len(state["jobs"]) == 1


def test_prepare_rejects_symlink_and_active_attempt(host):
    init(host)
    (host[0] / ".coordinator/worktrees").symlink_to(host[0].parent, target_is_directory=True)
    assert "symlink" in run(host, "workspace", "prepare", ok=False).stderr
    state_path = host[0] / ".coordinator/g/goal.json"
    state = json.loads(state_path.read_text())
    state["jobs"] = [{"transport_status":"unknown", "agent":"codex"}]
    state_path.write_text(json.dumps(state))
    assert "active or unknown" in run(host, "workspace", "prepare", ok=False).stderr


def test_controller_lock_refuses_concurrent_mutation(host):
    init(host)
    lock = host[0] / ".coordinator/g/controller.lock"
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert "another controller" in run(host, "workspace", "prepare", ok=False).stderr
        assert run(host, "workspace", "status")["workspaces"] == {}


def test_review_dispatch_and_retry_use_worker_result_path(host):
    source = collected_candidate(host)
    reviewer = Path(run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r")["workspace"]["path"])
    dispatched = run(host, "dispatch", "--round", "r", "--role", "reviewer", "--transport-dir", str(host[2]))
    assert dispatched["job"]["workdir"] == str(reviewer)
    assert dispatched["job"]["effort"] == "medium"
    # The fake transport writes an implementation-shaped result: this is an
    # infrastructure failure, not acceptance or a reason to modify the candidate.
    result = run(host, "collect", "--round", "r", "--role", "reviewer")
    assert result["outcome"] == "infrastructure-failure"
    run(host, "retry", "--round", "r", "--role", "reviewer", "--note", "fake malformed result")
    assert not (reviewer / ".coordinator/g/reviews/r.json").exists()
    assert list((reviewer / ".coordinator/g/reviews").glob("r-set-aside-*.json"))
    assert (source / "source.bin").read_bytes() == b"baseline\x00\xff"


@pytest.mark.parametrize("override", ["../outside", ".env"])
def test_freeze_refuses_unsafe_or_ignored_include(host, override):
    collected_candidate(host)
    denied = run(host, "workspace", "prepare", "--role", "reviewer", "--round", "r",
                 "--include-untracked", override, ok=False)
    assert denied.returncode != 0


def test_generated_ignore_does_not_follow_a_symlink(host):
    outside = host[0].parent / "outside.txt"
    outside.write_text("preserve user content")
    (host[0] / ".coordinator/.gitignore").symlink_to(outside)
    result = run(host, "init", "--objective", "fixture", ok=False)
    assert result.returncode != 0
    assert "symlink" in result.stderr
    assert outside.read_text() == "preserve user content"
