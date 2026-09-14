#!/usr/bin/env python3
"""Drive the coordinator state machine for one goal.

The script owns bookkeeping (goal.json / ledger.json), guarded transitions,
transport dispatch through the coding-agent Skill, and mechanical envelope
validation. It never adjudicates: the coordinator reads the facts this script
reports and calls `advance` explicitly. A `go` verdict from this script means
"the envelope satisfies the mechanical shape", not "the work is accepted".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workspace import WorkspaceError, capture, create, git, goal_lock, identity, safe_path, verify

SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_GUARD = 2

TERMINAL_STATES = {"completed"}
# blocked is a holding state (bound exhausted / no transport), not death:
# a user decision can resume the goal via human-gate.
# Role-driven transitions happen inside freeze/dispatch/retry. This table
# covers the coordinator-driven `advance` command only.
ADVANCE_TRANSITIONS = {
    "reviewing": {"ready", "repairing", "completed"},
    "human-gate": {"ready", "repairing", "completed"},
}
HOLDING_STATES = {"human-gate", "blocked"}

# The runner already knows these (role/round from the dispatch, start_revision
# from goal.json, schema_version from this file). Asking the worker to
# transcribe registry data is pure failure surface — every transcribed field
# is a chance to improvise. Missing runner-known fields are auto-filled at
# collect; present-but-inconsistent ones are infrastructure failures.
RUNNER_KNOWN = {"schema_version", "role", "round_id", "start_revision"}

IMPLEMENTER_REQUIRED = {
    "schema_version",
    "role",
    "status",
    "round_id",
    "start_revision",
    "candidate_revision",
    "changed_files",
    "commands",
    "unresolved",
    "summary",
}
REVIEWER_REQUIRED = {
    "schema_version",
    "role",
    "verdict",
    "round_id",
    "start_revision",
    "candidate_revision",
    "checks",
    "blockers",
    "spec_uncertainties",
    "infrastructure_errors",
}


class InputError(Exception):
    """Caller supplied an unusable request."""


class GuardError(Exception):
    """The state machine forbids this transition or action."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    lines = [f"{key}: {value}" for key, value in payload.items() if key != "errors"]
    print("\n".join(lines))
    for error in payload.get("errors", []):
        print(f"error: {error}", file=sys.stderr)


def fail(message: str, kind=InputError) -> None:
    raise kind(message)


def atomic_write(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as tmp:
        tmp.write(text)
    os.replace(tmp.name, path)


def load_json(path: Path, what: str) -> dict:
    if not path.is_file():
        fail(f"{what} not found at {path}; use `init` first")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        fail(f"{what} at {path} is malformed; inspect it by hand")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_dir(goal_id: str) -> Path:
    """Return host-private state for a goal, outside the role-visible worktree."""
    override = os.environ.get("COORDINATOR_STATE_DIR")
    if override:
        root = Path(override).expanduser()
    else:
        state_home = os.environ.get("XDG_STATE_HOME")
        root = (
            Path(state_home).expanduser() / "coordinator"
            if state_home
            else Path.home() / ".local" / "state" / "coordinator"
        )
    return root / goal_id


# Dispatch appends the role's envelope schema as the FINAL prompt segment.
# Hard-won lesson (goal inv-recon-74 / verdict-taxonomy): a schema embedded in
# a long contract loses to the worker's attention budget — the worker improvises
# field names, three malformed envelopes in a row. The tail below is injected
# by the runner itself so it is identical and last on every dispatch, no matter
# what the contract says or what other schemas are visible nearby.
ENVELOPE_TAILS = {
    "implementer": """
═══ 交付信封 schema（机械校验，优先级高于上文一切格式暗示）═══
把你的交付 JSON 写到：{result_path}（就是这个路径，别找别处）。
你**必须**提供的字段：
{"status":"completed"或"blocked",
"candidate_revision":"<commit sha 或 uncommitted-working-tree>",
"changed_files":[...],
"commands":[{"command":"真实跑过的命令","exit_code":0},...],
"unresolved":[...],"summary":"..."}
登记字段（schema_version/role/round_id/start_revision）由 runner 自动补齐，
你不用写；若写，必须与事实完全一致（round_id 不是 round，不一致即拒收）。
status 只有 completed|blocked；命令证据放 commands 数组。
""",
    "reviewer": """
═══ 裁决信封 schema（机械校验，优先级高于上文一切格式暗示）═══
把裁决 JSON 写到：{result_path}（就是这个路径，别找别处）。
你**必须**提供的字段：
{"verdict":"go"或"no-go",
"candidate_revision":"...",
"checks":[{"id":"...","kind":"open"或"withheld","required":true,
"passed":true或false,"evidence":"命令+结果"},...],
"blockers":[...],"spec_uncertainties":[...],"infrastructure_errors":[...]}
登记字段（schema_version/role/round_id/start_revision）由 runner 自动补齐，
你不用写；若写，必须与事实完全一致。verdict 只有 go|no-go。
环境或沙箱阻止检查时记入 infrastructure_errors，不当作代码缺陷；只使用合同预先授权的替代证据，不放宽门禁或自行绕过权限。
""",
}


def build_dispatch_prompt(role: str, contract: Path, result_path: str) -> str:
    return (
        contract.read_text(encoding="utf-8")
        + ENVELOPE_TAILS[role].replace("{result_path}", result_path)
    )


class Goal:
    def __init__(self, workdir: Path, goal_id: str):
        if not goal_id or "/" in goal_id or goal_id.startswith("."):
            fail("goal-id must be a plain path segment")
        self.dir = workdir / ".coordinator" / goal_id
        self.goal_path = self.dir / "goal.json"
        self.ledger_path = self.dir / "ledger.json"
        self.data = load_json(self.goal_path, "goal.json")
        self.ledger = load_json(self.ledger_path, "ledger.json")

    @property
    def state(self) -> str:
        return self.data["state"]

    def require_state(self, allowed: set[str], action: str) -> None:
        if self.state not in allowed:
            raise GuardError(
                f"cannot {action} from state {self.state!r}; allowed: {sorted(allowed)}"
            )

    def set_state(self, state: str) -> None:
        self.data["state"] = state
        self.data["updated_at"] = now_iso()

    def save(self) -> None:
        atomic_write(self.goal_path, json.dumps(self.data, indent=2, sort_keys=True) + "\n")
        atomic_write(
            self.ledger_path, json.dumps(self.ledger, indent=2, sort_keys=True) + "\n"
        )

    def round_entry(self, round_id: str) -> dict:
        return self.ledger.setdefault("rounds", {}).setdefault(round_id, {})


def resolve_transport_dir(explicit: str | None) -> Path:
    candidate = (
        explicit
        or os.environ.get("CODING_AGENT_DIR")
        or str(Path(__file__).resolve().parents[2] / "coding-agent")
    )
    runner = Path(candidate) / "scripts" / "coding-agent-run"
    if not runner.is_file():
        fail(
            f"coding-agent transport not found at {runner}; "
            "pass --transport-dir or set CODING_AGENT_DIR"
        )
    return runner


def find_job(goal: Goal, round_id: str, role: str) -> dict:
    for job in reversed(goal.data.get("jobs", [])):
        if job["round_id"] == round_id and job["role"] == role:
            return job
    fail(f"no {role} dispatch recorded for {round_id}; use `dispatch` first")


def cmd_init(args: argparse.Namespace) -> dict:
    workdir = Path(args.workdir).resolve()
    if not workdir.is_dir():
        fail(f"workdir {workdir} does not exist")
    if not args.goal_id or "/" in args.goal_id or args.goal_id.startswith("."):
        fail("goal-id must be a plain path segment")
    goal_dir = workdir / ".coordinator" / args.goal_id
    if goal_dir.exists():
        fail(f"goal directory {goal_dir} already exists; pick a new goal-id")
    ensure_runtime_ignore(workdir)
    for sub in ("contracts", "deliveries", "reviews"):
        (goal_dir / sub).mkdir(parents=True)
    revision = args.start_revision
    if not revision:
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            revision = None
    goal_record = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": args.goal_id,
        "objective": args.objective,
        "mode": args.mode,
        "state": "establishing",
        "resume_state": None,
        "start_revision": revision,
        "current_round": None,
        "transport": "coding-agent",
        "repair_bound": args.repair_bound,
        "repairs_used": 0,
        "jobs": [],
        "updated_at": now_iso(),
    }
    ledger = {"schema_version": SCHEMA_VERSION, "goal_id": args.goal_id, "rounds": {}}
    atomic_write(goal_dir / "goal.json", json.dumps(goal_record, indent=2, sort_keys=True) + "\n")
    atomic_write(
        goal_dir / "ledger.json", json.dumps(ledger, indent=2, sort_keys=True) + "\n"
    )
    (goal_dir / "constraints.md").write_text(
        "# Constraints\n\nInvariants, scope, and gates for this goal.\n",
        encoding="utf-8",
    )
    return {
        "command": "init",
        "goal_id": args.goal_id,
        "state": "establishing",
        "goal_dir": str(goal_dir),
        "start_revision": revision,
        "errors": [],
    }


def cmd_freeze(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    if args.role == "implementer":
        # An implementer freeze is the go signal: it advances the goal.
        goal.require_state({"establishing", "ready", "repairing"}, "freeze a contract")
        if goal.state == "ready":
            # ready also means "frozen, awaiting dispatch". Only a reviewed
            # round may be followed by a new one, so a pending round is never
            # silently skipped, and a frozen contract is never refrozen.
            current = goal.data.get("current_round")
            if goal.round_entry(current).get("reviewer", {}).get("outcome") != "collected":
                raise GuardError(
                    f"round {current} has no collected review; dispatch it before freezing another round"
                )
            if goal.round_entry(args.round).get("contract"):
                raise GuardError(f"round {args.round} already has a frozen contract; freeze a new round")
    else:
        # A review contract is bookkeeping prepared around the dispatch; it
        # must never move the state machine backwards or forwards.
        goal.require_state(
            {"establishing", "ready", "implementing", "repairing"},
            "freeze a review contract",
        )
    source = Path(args.contract)
    if not source.is_file():
        fail(f"contract file {source} not found")
    suffix = "-review" if args.role == "reviewer" else ""
    # Reviewer contracts can contain withheld checks. Freeze them in host-private
    # state; only legacy goals may retain a reviewer contract in the worktree.
    contract_dir = (
        private_dir(args.goal_id) / "contracts"
        if args.role == "reviewer"
        else goal.dir / "contracts"
    )
    contract_dir.mkdir(parents=True, exist_ok=True)
    target = contract_dir / f"{args.round}{suffix}.md"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    entry = goal.round_entry(args.round)
    key = "review_contract" if args.role == "reviewer" else "contract"
    if args.role == "reviewer":
        entry[key] = {"sha256": sha256_file(target), "private": True}
    else:
        entry[key] = {"path": str(target), "sha256": sha256_file(target)}
    if args.role == "implementer":
        goal.data["current_round"] = args.round
        goal.set_state("ready")
    goal.save()
    return {
        "command": "freeze",
        "goal_id": args.goal_id,
        "round_id": args.round,
        "role": args.role,
        "state": goal.state,
        "contract_sha256": entry[key]["sha256"],
        "errors": [],
    }


def workspace_key(role: str, round_id: str | None) -> str:
    if role == "reviewer" and (not round_id or "/" in round_id or round_id.startswith(".")):
        fail("review workspace requires a plain --round path segment")
    return "implementer" if role == "implementer" else f"reviewer:{round_id}"


def require_quiescent(goal: Goal) -> None:
    for job in goal.data.get("jobs", []):
        refresh_job(goal, job)
        if job.get("transport_status") not in {"completed", "failed", "cancelled", "timeout"}:
            raise GuardError("workspace operation refused while a worker is active or unknown")


def cmd_workspace(args: argparse.Namespace) -> dict:
    control = Path(args.workdir).resolve()
    goal = Goal(control, args.goal_id)
    records = goal.data.get("workspaces", {})
    if args.action == "status":
        observations = {}
        for key, record in records.items():
            try:
                path = verify(record, control)
                observations[key] = {**record, "valid": True,
                    "head": git(path, "rev-parse", "HEAD").decode().strip(),
                    "changes": os.fsdecode(git(path, "status", "--porcelain"))}
            except WorkspaceError as exc:
                observations[key] = {**record, "valid": False, "error": str(exc)}
        return {"command": "workspace", "action": "status", "workspaces": observations, "errors": []}
    key = workspace_key(args.role, args.round)
    require_quiescent(goal)
    safe_path(control, control / ".coordinator")
    safe_path(control, goal.dir / "snapshots")
    repository = identity(control)
    # worktree registration writes shared Git metadata as well as local files.
    if not Path(repository["common_dir"]).is_relative_to(control):
        fail("prepare must run from the control checkout containing shared Git metadata")
    if key in records:
        path = verify(records[key], control)
        if args.base and git(control, "rev-parse", "--verify", args.base + "^{commit}").decode().strip() != records[key]["base_revision"]:
            fail("registered workspace uses a different base; do not reset it")
        return {"command": "workspace", "action": "prepare", "status": "reused",
                "workspace": records[key], "config_path": str(config_path(args)), "errors": []}
    snapshot = None
    if args.role == "implementer":
        base = args.base or goal.data.get("start_revision")
        if not base or base.startswith("-"):
            fail("workspace preparation requires a valid starting commit")
        base = git(control, "rev-parse", "--verify", base + "^{commit}").decode().strip()
        if base != goal.data.get("start_revision"):
            fail("workspace base must match the goal's starting revision")
        path = control / ".coordinator/worktrees" / args.goal_id / "implementer"
    else:
        if args.base:
            fail("review workspace uses the captured candidate, not --base")
        if goal.round_entry(args.round).get("implementer", {}).get("outcome") != "collected":
            fail("collect the implementation before preparing its review workspace")
        source_record = records.get("implementer")
        if not source_record:
            fail("prepare a managed implementer workspace first")
        source = verify(source_record, control)
        snapshot = capture(source, goal.dir / "snapshots", args.include_untracked)
        base = snapshot["head"]
        path = control / ".coordinator/worktrees" / args.goal_id / "reviewer" / args.round
    safe_path(control, path)
    ensure_runtime_ignore(control)
    record = create(control, path, base, snapshot["tree"] if snapshot else None)
    ensure_runtime_ignore(path)
    if snapshot:
        if capture(source, goal.dir / "snapshots", args.include_untracked) != snapshot:
            fail("candidate changed during freeze; checkout retained for inspection")
        record["candidate"] = snapshot
        atomic_write(goal.dir / "snapshots" / f"{args.round}.json", json.dumps(snapshot))
        (goal.dir / "snapshots" / f"{args.round}.patch").write_bytes(git(source, "diff", "--binary", base, snapshot["tree"]))
    goal.data.setdefault("workspaces", {})[key] = record
    goal.save()
    return {"command": "workspace", "action": "prepare", "status": "created",
            "workspace": record, "config_path": str(config_path(args)), "errors": []}


def dispatch_workspace(goal: Goal, control: Path, role: str, round_id: str, env: dict) -> Path:
    require_quiescent(goal)
    redirects = {"GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_NAMESPACE"}
    if redirects & env.keys():
        fail("remove inherited/transport Git identity overrides before workspace dispatch")
    records = goal.data.get("workspaces", {})
    if records:
        safe_path(control, goal.dir / "snapshots")
        record = records.get(workspace_key(role, round_id))
        if not record:
            fail("workspace setup required: run workspace prepare for this role/round")
        path = verify(record, control)
        if role == "reviewer":
            frozen = record["candidate"]
            source = verify(records["implementer"], control)
            if capture(source, goal.dir / "snapshots", frozen["include_untracked"]) != frozen:
                fail("implementation changed since candidate freeze")
            current = capture(path, goal.dir / "snapshots", [])
            if (current["head"], current["tree"]) != (frozen["head"], frozen["tree"]):
                fail("review workspace no longer matches the frozen candidate")
        return path
    # Compatible external hosts can supply an existing linked worktree. Git
    # control checkouts are never accepted as execution roots. Non-Git transports
    # remain protocol-only; they must supply their own workspace boundary.
    probe = subprocess.run(["git", "-C", str(control), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, timeout=10)
    if probe.returncode == 0:
        actual = identity(control)
        if actual["git_dir"] == actual["common_dir"]:
            fail("workspace setup required: control checkout cannot execute workers; run workspace prepare")
    return control


CONFIG_AGENTS = {"codex", "tcodex", "agy", "claude", "tclaude"}


def review_pair_allowed(implementer: dict, reviewer: dict) -> bool:
    return (implementer["agent"] != reviewer["agent"] or
            bool(implementer.get("model") and reviewer.get("model")
                 and implementer["model"] != reviewer["model"]))


def config_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "config", None) or os.environ.get("COORDINATOR_CONFIG")
    return Path(explicit).expanduser().resolve() if explicit else Path(args.workdir).resolve() / ".coordinator/config.json"


def validate_config(payload: object, *, check_pair: bool = True) -> dict:
    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload.get("schema_version") != 1):
        fail("config must be an object with schema_version 1")
    if payload.keys() - {"schema_version", "implementer", "reviewer", "execution"}:
        fail("config contains unknown fields; do not store credentials or broad execution permissions here")
    execution = payload.get("execution", {})
    if (not isinstance(execution, dict) or execution.keys() - {"local_commits"}
            or ("local_commits" in execution and type(execution["local_commits"]) is not bool)):
        fail("execution accepts only optional boolean local_commits")
    for role in ("implementer", "reviewer"):
        candidates = payload.get(role)
        if not isinstance(candidates, list) or not candidates:
            fail(f"config {role} must be a nonempty ordered candidate array")
        for candidate in candidates:
            if (not isinstance(candidate, dict) or not isinstance(candidate.get("agent"), str)
                    or candidate["agent"] not in CONFIG_AGENTS):
                fail(f"config {role} contains an unsupported agent")
            if candidate.keys() - {"agent", "model", "effort"}:
                fail("candidate fields are agent, model and optional effort only")
            model = candidate.get("model")
            if (not isinstance(model, str) or not model or model.startswith("-")
                    or any(c.isspace() for c in model)
                    or any(token in model for token in ("*", ">", "<", "+", "以上"))):
                fail("config models must be concrete CLI model IDs, not family names or version ranges")
            effort = candidate.get("effort")
            if effort is not None and (not isinstance(effort, str) or effort not in {"low", "medium", "high", "xhigh", "max"}):
                fail("config effort is invalid")
            if candidate["agent"] == "agy" and (role == "reviewer" or effort not in {"low", "medium", "high"}):
                fail("agy is implementation-only and requires low/medium/high effort")
    if check_pair and not any(review_pair_allowed(i, r) for i in payload["implementer"] for r in payload["reviewer"]):
        fail("config needs at least one distinct provider/model implementer/reviewer pairing")
    return payload


def load_config(args: argparse.Namespace) -> dict:
    path = config_path(args)
    if not path.is_file():
        raise GuardError(f"setup required: missing {path}; run coordinator_goal.py setup first")
    try:
        return validate_config(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid coordinator config {path}: {exc}")


def probe_candidate(candidate: dict, env: dict) -> None:
    agent = candidate["agent"]
    command = [agent, "--", "--help"] if agent in {"tcodex", "tclaude"} else [agent, "--help"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"{agent} preflight failed: {exc}")
    flags = ["--model"]
    if candidate.get("effort") and agent not in {"codex", "tcodex"}:
        flags += ["--effort"]
    if agent == "agy":
        flags += ["--input-format", "--output-format", "--json-schema", "--sandbox"]
    if result.returncode or any(flag not in result.stdout for flag in flags):
        fail(f"{agent} CLI does not expose required model/effort/transport flags")


def cmd_setup(args: argparse.Namespace) -> dict:
    if not args.from_file:
        return {"command": "setup", "status": "confirmation-required", "config_path": str(config_path(args)),
                "installed_agents": sorted(agent for agent in CONFIG_AGENTS if shutil.which(agent)),
                "recommendations": [
                    {"agent": "codex", "model": "gpt-5.6-luna", "effort": "high"},
                    {"agent": "agy", "model_requirement": "Gemini Flash 3.8 or newer Flash", "effort": "high"},
                    {"agent": "tclaude", "model_requirement": "DeepSeek Flash v4 or newer Flash"}],
                "reviewer_recommendations": [{"agent": "codex", "model": "gpt-5.6-sol", "effort": "medium"}],
                "execution_recommendations": {"local_commits": True},
                "required": "Confirm concrete model IDs, ordered implementers, an independent reviewer and local worktree commit authorization; then setup --from-file FILE",
                "errors": []}
    try:
        config = validate_config(json.loads(Path(args.from_file).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read setup input: {exc}")
    path = config_path(args)
    if not path.is_relative_to(Path(args.workdir).resolve()) and not args.config:
        fail("outside-workspace setup requires an explicitly authorized --config destination")
    if path.exists():
        fail("config already exists; review and edit it explicitly rather than overwriting via setup")
    if not Path(args.workdir).resolve().is_dir():
        fail("workdir does not exist")
    for role in ("implementer", "reviewer"):
        for candidate in config[role]:
            probe_candidate(candidate, os.environ.copy())
    if path == Path(args.workdir).resolve() / ".coordinator/config.json":
        ensure_runtime_ignore(Path(args.workdir).resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    return {"command": "setup", "status": "configured", "config_path": str(path), "errors": []}


def cmd_dispatch(args: argparse.Namespace) -> dict:
    config = load_config(args)
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    workdir = Path(args.workdir).resolve()
    env = {**os.environ, **(args.transport_env or {})}
    workdir = dispatch_workspace(goal, workdir, args.role, args.round, env)
    local_commits = False
    if args.role == "implementer" and config.get("execution", {}).get("local_commits", False):
        try:
            workspace_identity = identity(workdir)
            local_commits = workspace_identity["git_dir"] != workspace_identity["common_dir"]
        except WorkspaceError:
            pass  # Non-Git protocol-only roots cannot inherit Git authorization.
    commit_policy = (
        "Local milestone commits are authorized in this worktree, subject to host rules and task restrictions: disclose before committing; stage explicit task files only, excluding secrets and runtime output. "
        "Commit one coherent, reviewable, independently revertible change after relevant checks pass; include its tests/docs and explain its intent. "
        "Consider checkpoints every 30-60 minutes and before handoff, without forcing incomplete or fragmented commits; report remaining work and blockers. "
        "No push, merge, history rewrite, other branches/tags or cleanup; commits are not acceptance.\n"
        if local_commits else
        "No local commit authorization is inherited for this dispatch. Do not commit unless the user explicitly authorizes it for this task.\n"
    )
    candidates = [dict(c) for c in config[args.role]]
    if args.agent != "auto":
        candidates = [c for c in candidates if c["agent"] == args.agent]
    for candidate in candidates:
        if args.model is not None:
            candidate["model"] = args.model
        if args.effort is not None:
            candidate["effort"] = args.effort
    candidates = [c for c in candidates if shutil.which(c["agent"], path=env.get("PATH"))]
    if args.role == "implementer":
        reviewers = [c for c in config["reviewer"] if shutil.which(c["agent"], path=env.get("PATH"))]
        candidates = [c for c in candidates if any(review_pair_allowed(c, r) for r in reviewers)]
    else:
        implementer = find_job(goal, args.round, "implementer")
        candidates = [c for c in candidates if review_pair_allowed(implementer, c)]
        # Stable partition: prefer a different provider, preserving configured
        # order within each group. Model diversity is only the fallback.
        candidates.sort(key=lambda c: c["agent"] == implementer["agent"])
    if not candidates:
        fail("no installed configured candidate with a distinct provider/model review pairing")
    selected = dict(candidates[0])
    # Pair eligibility above uses resolved settings and the actual execution
    # job. Do not recheck review against stale implementation defaults here.
    validate_config({**config, args.role: [selected]}, check_pair=False)
    probe_candidate(selected, env)
    args.agent = selected["agent"]
    if args.role == "implementer":
        goal.require_state({"ready"}, "dispatch an implementer")
        if goal.data.get("current_round") != args.round:
            fail(
                f"current round is {goal.data.get('current_round')!r}, "
                f"not {args.round!r}; freeze the implementer contract first"
            )
        result_rel = f".coordinator/{args.goal_id}/deliveries/{args.round}.json"
    else:
        goal.require_state({"implementing"}, "dispatch a reviewer")
        entry = goal.round_entry(args.round)
        delivery = entry.get("implementer", {})
        if delivery.get("outcome") != "collected":
            fail(
                f"no collected implementer delivery for {args.round}; "
                "use `collect --role implementer` first"
            )
        result_rel = f".coordinator/{args.goal_id}/reviews/{args.round}.json"
    suffix = "-review" if args.role == "reviewer" else ""
    public_contract = goal.dir / "contracts" / f"{args.round}{suffix}.md"
    if args.role == "reviewer":
        private_contract = private_dir(args.goal_id) / "contracts" / public_contract.name
        # Compatibility for goals frozen before reviewer contracts became private.
        contract = private_contract if private_contract.is_file() else public_contract
    else:
        contract = public_contract
    if not contract.is_file():
        fail(f"contract {contract} not found; freeze it first")

    runner = resolve_transport_dir(args.transport_dir)
    if args.agent == "agy" and args.role != "implementer":
        fail("agy adapter does not enforce read-only review; choose an authorized read-only reviewer")
    if args.agent == "agy":
        adapter = runner.parent / "structured_run.py"
        if not adapter.is_file():
            adapter = runner.parent / "codex_run.py"
        if not adapter.is_file():
            fail("installed coding-agent transport lacks the agy structured adapter")
    # Materialize reviewer prompts beside the private contract so neither the
    # withheld checks nor the injected copy becomes visible in the worktree.
    prompt_dir = (
        private_dir(args.goal_id) / "contracts"
        if args.role == "reviewer"
        else goal.dir / "contracts"
    )
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{args.round}{suffix}.prompt.md"
    atomic_write(
        prompt_file, commit_policy + build_dispatch_prompt(args.role, contract, result_rel)
    )
    if workdir != Path(args.workdir).resolve():
        public_dir = workdir / ".coordinator" / args.goal_id
        safe_path(workdir, public_dir)
        for sub in ("contracts", "deliveries", "reviews"):
            (public_dir / sub).mkdir(parents=True, exist_ok=True)
        for name in ("constraints.md", "ledger.json"):
            atomic_write(public_dir / name, (goal.dir / name).read_text(encoding="utf-8"))
        if args.role == "implementer":
            atomic_write(public_dir / "contracts" / contract.name, contract.read_text(encoding="utf-8"))
        atomic_write(prompt_file, f"Execution root: {workdir}\nControl files are managed by the coordinator; do not enter the control checkout or create another worktree.\n" + prompt_file.read_text())
    command = [
        "bash",
        str(runner),
        "run",
        "--agent",
        args.agent,
        "--workdir",
        str(workdir),
        "--prompt-file",
        str(prompt_file),
        "--result-file",
        result_rel,
        "--json",
    ]
    command += ["--model", selected["model"]]
    if selected.get("effort"):
        command += ["--effort", selected["effort"]]
    job = {
        "round_id": args.round, "role": args.role, "agent": args.agent,
        "session_id": None, "dispatched_at": now_iso(),
        "transport_status": "unknown", "worker_exit_code": None,
        "result_artifact": None,
        "model": selected["model"], "effort": selected.get("effort"),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest(),
        "workdir": str(workdir), "result_path": str(workdir / result_rel),
        "local_commits": local_commits,
    }
    if args.agent != "agy":
        state_root = (env.get("CODING_AGENT_STATE_DIR") or
                      (str(Path(env["XDG_STATE_HOME"]) / "coding-agent") if env.get("XDG_STATE_HOME")
                       else str(Path(env.get("HOME", str(Path.home()))) / ".local/state/coding-agent")))
        job["transport_runner"] = str(runner.resolve())
        job["transport_state_dir"] = str(Path(state_root).expanduser().resolve())
        command += ["--state-dir", job["transport_state_dir"]]
    if args.agent == "agy":
        state_dir = private_dir(args.goal_id) / "transport"
        if (workdir / result_rel).exists():
            fail("delivery path already exists; collect or set aside the old attempt first")
        job["session_id"] = f"agy-{uuid.uuid4().hex}"
        job["adapter"] = str(adapter)
        schema_file = prompt_dir / f"{args.round}.schema.json"
        atomic_write(schema_file, json.dumps({
            "type": "object", "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["completed", "blocked"]},
                "candidate_revision": {"type": "string"},
                "changed_files": {"type": "array", "items": {"type": "string"}},
                "commands": {"type": "array", "items": {"type": "object"}},
                "unresolved": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
            "required": ["status", "candidate_revision", "changed_files", "commands", "unresolved", "summary"],
        }))
        atomic_write(prompt_file, commit_policy + contract.read_text(encoding="utf-8") +
                     "\nReturn the delivery as structured_output matching the supplied schema. Do not write the delivery file.\n")
        if workdir != Path(args.workdir).resolve():
            atomic_write(prompt_file, f"Execution root: {workdir}\nDo not enter the control checkout or create another worktree.\n" + prompt_file.read_text())
        command = [sys.executable, str(adapter), "start", "--agent", "agy", "--write",
                   "--workdir", str(workdir), "--prompt-file", str(prompt_file),
                   "--output-schema", str(schema_file), "--state-dir", str(state_dir),
                   "--job-id", job["session_id"],
                   "--timeout", str(args.timeout), "--json"]
        command += ["--model", selected["model"], "--effort", selected["effort"]]
    # Persist the attempt before launch: a host timeout is not evidence that
    # the worker stopped, and must never reopen the round automatically.
    goal.data.setdefault("jobs", []).append(job)
    goal.set_state("implementing" if args.role == "implementer" else "reviewing")
    goal.save()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=args.timeout + 10 if args.agent == "agy" else args.timeout,
            env={**os.environ, **(args.transport_env or {})},
        )
    except subprocess.TimeoutExpired:
        raise GuardError(f"transport did not return within {args.timeout}s")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise GuardError(
            f"transport returned no parseable envelope (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:200] or proc.stdout.strip()[:200]}"
        )

    if not isinstance(envelope, dict):
        fail("transport envelope must be an object; attempt remains unknown")
    if envelope.get("agent", args.agent) != args.agent or envelope.get("workdir", str(workdir)) != str(workdir):
        fail("transport provider/workdir mismatch; attempt remains unknown")
    if args.agent == "agy":
        if envelope.get("job_id") != job["session_id"] or envelope.get("workdir") != str(workdir):
            fail("native transport identity/workdir mismatch; attempt remains unknown")
        if envelope.get("status") == "completed" and isinstance(envelope.get("structured_output"), dict):
            atomic_write(goal.dir / "deliveries" / f"{args.round}.json", json.dumps(envelope["structured_output"]))
        envelope["session_id"] = envelope.get("job_id")
        envelope["worker_exit_code"] = envelope.get("exit_code")
        job["activity"] = envelope.get("activity")
        job["conversation_id"] = envelope.get("thread_id")
    job.update({
        "session_id": envelope.get("session_id"),
        "agent": envelope.get("agent", args.agent),
        "transport_status": envelope.get("status"),
        "worker_exit_code": envelope.get("worker_exit_code"),
        "result_artifact": envelope.get("result_artifact", {}).get("status"),
    })
    goal.save()
    return {
        "command": "dispatch",
        "goal_id": args.goal_id,
        "state": goal.state,
        "job": job,
        "errors": envelope.get("errors", []),
    }


def validate_envelope(role: str, payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["envelope is not a JSON object"]
    errors: list[str] = []
    required = IMPLEMENTER_REQUIRED if role == "implementer" else REVIEWER_REQUIRED
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {payload.get('schema_version')!r}")
    if payload.get("role") != role:
        errors.append(f"role is {payload.get('role')!r}, expected {role!r}")
    arrays = ("changed_files", "commands", "unresolved") if role == "implementer" else (
        "checks", "blockers", "spec_uncertainties", "infrastructure_errors")
    for field in arrays:
        if not isinstance(payload.get(field), list):
            errors.append(f"{field} must be an array")
    objects = "commands" if role == "implementer" else "checks"
    if isinstance(payload.get(objects), list) and any(not isinstance(item, dict) for item in payload[objects]):
        errors.append(f"{objects} entries must be objects")
    if role == "reviewer" and isinstance(payload.get("checks"), list):
        for check in payload["checks"]:
            if not isinstance(check, dict):
                continue
            if not isinstance(check.get("id"), str) or check.get("kind") not in {"open", "withheld"}:
                errors.append("checks require string id and open/withheld kind")
            if type(check.get("required")) is not bool or type(check.get("passed")) is not bool:
                errors.append("checks required/passed must be booleans")
            for field in ("evidence", "evidence_ref"):
                if field in check and not isinstance(check[field], str):
                    errors.append(f"check {field} must be a string")
    for field in ("round_id", "candidate_revision", "summary"):
        if field in payload and not isinstance(payload[field], str):
            errors.append(f"{field} must be a string")
    if role == "implementer":
        if payload.get("status") not in {"completed", "blocked"}:
            errors.append(f"implementation status {payload.get('status')!r} invalid")
    else:
        if payload.get("verdict") not in {"go", "no-go"}:
            errors.append(f"review verdict {payload.get('verdict')!r} invalid")
    return errors


def mechanical_go(payload: dict) -> bool:
    """The review contract's mechanical `go` shape, no adjudication."""
    if payload.get("verdict") != "go":
        return False
    for check in payload.get("checks", []):
        if check.get("required") and not check.get("passed"):
            return False
        if check.get("required") and not (
            check.get("evidence") or check.get("evidence_ref")
        ):
            return False
    return not (
        payload.get("blockers")
        or payload.get("spec_uncertainties")
        or payload.get("infrastructure_errors")
    )


def cmd_collect(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    job = find_job(goal, args.round, args.role)
    native = refresh_job(goal, job)
    if job.get("transport_status") not in {"completed", "failed", "cancelled", "timeout"}:
        fail("cannot collect an active or unknown attempt; establish terminal transport state first")
    if job.get("transport_status") != "completed":
        fail("execution did not complete successfully; treat this attempt as infrastructure failure")
    rel = (
        f"deliveries/{args.round}.json"
        if args.role == "implementer"
        else f"reviews/{args.round}.json"
    )
    artifact = goal.dir / rel
    source = Path(job.get("result_path", str(artifact)))
    if not native and source != artifact and source.exists():
        worker_root = Path(job["workdir"])
        if (source.is_symlink() or not source.resolve().is_relative_to(worker_root)
                or not source.is_file() or source.stat().st_size > 1048576):
            fail("worker result artifact is unsafe or too large")
        if artifact.exists() and artifact.read_bytes() != source.read_bytes():
            fail("collected artifact differs from this worker's result")
        if not artifact.exists():
            atomic_write(artifact, source.read_text(encoding="utf-8"))
    if native and job.get("transport_status") == "completed" and isinstance(native.get("structured_output"), dict):
        if not artifact.exists():
            atomic_write(artifact, json.dumps(native["structured_output"]))
        else:
            try:
                stored = json.loads(artifact.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                stored = None
            if stored != native["structured_output"]:
                fail("delivery differs from this job's native structured result")
    entry = goal.round_entry(args.round)
    outcome: dict
    if not artifact.is_file():
        outcome = {
            "outcome": "infrastructure-failure",
            "detail": f"result artifact {artifact} is missing",
        }
    else:
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        autofilled: list[str] = []
        inconsistent: list[str] = []
        if isinstance(payload, dict):
            known = {
                "schema_version": SCHEMA_VERSION,
                "role": args.role,
                "round_id": args.round,
                "start_revision": goal.data.get("start_revision"),
            }
            inconsistent = [
                k for k in sorted(RUNNER_KNOWN)
                if k in payload and known[k] is not None and payload[k] != known[k]
            ]
            if not inconsistent:
                for k in RUNNER_KNOWN:
                    if k not in payload:
                        payload[k] = known[k]
                        autofilled.append(k)
        if not isinstance(payload, dict):
            problems = ["envelope is not a JSON object"]
        elif inconsistent:
            problems = [
                "runner-known fields inconsistent: " + ", ".join(inconsistent)
            ]
        else:
            problems = validate_envelope(args.role, payload)
        if problems:
            outcome = {"outcome": "infrastructure-failure", "detail": "; ".join(problems)}
        else:
            outcome = {"outcome": "collected"}
            if autofilled:
                outcome["autofilled"] = sorted(autofilled)
            if args.role == "implementer":
                outcome["status"] = payload["status"]
                outcome["candidate_revision"] = payload["candidate_revision"]
            else:
                outcome["verdict"] = payload["verdict"]
                outcome["mechanical_go"] = mechanical_go(payload)
                if payload["infrastructure_errors"]:
                    outcome["outcome"] = "infrastructure-failure"
                    outcome["detail"] = "review checks were obstructed by infrastructure; candidate remains undecided"
    entry[args.role] = {**outcome, "job": job, "collected_at": now_iso()}
    goal.save()
    return {
        "command": "collect",
        "goal_id": args.goal_id,
        "round_id": args.round,
        "role": args.role,
        "state": goal.state,
        **outcome,
        "errors": [] if outcome["outcome"] == "collected" else [outcome["detail"]],
    }


def cmd_advance(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    current = goal.state
    target = args.to
    if current in TERMINAL_STATES:
        raise GuardError(f"goal is already {current}; no further transitions")
    if target in HOLDING_STATES:
        if target == "human-gate":
            goal.data["resume_state"] = current
    else:
        allowed = ADVANCE_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise GuardError(f"transition {current} -> {target} is not legal")
        if target == "repairing":
            used = goal.data.get("repairs_used", 0) + 1
            bound = goal.data.get("repair_bound")
            if bound is not None and used > bound:
                raise GuardError(
                    f"repair bound {bound} exhausted; advance to blocked instead"
                )
            goal.data["repairs_used"] = used
        if target == "completed":
            round_id = goal.data.get("current_round")
            review = goal.round_entry(round_id).get("reviewer", {}) if round_id else {}
            if not review.get("mechanical_go"):
                raise GuardError(
                    "cannot complete: no collected reviewer verdict with a "
                    "mechanical go on the current round"
                )
    goal.set_state(target)
    if args.note:
        goal.data["last_note"] = args.note
    goal.save()
    return {
        "command": "advance",
        "goal_id": args.goal_id,
        "from": current,
        "state": goal.state,
        "repairs_used": goal.data.get("repairs_used"),
        "errors": [],
    }


def cmd_retry(args: argparse.Namespace) -> dict:
    """Infrastructure retry: reopen the current round after a transport-level
    failure (missing/malformed envelope, stale-artifact refusal, dead worker).

    This is deliberately NOT a repair: the candidate was never judged, so the
    repair bound is not consumed. The role's resume state matches what
    `dispatch` requires (implementer dispatches from ready, reviewer from
    implementing).
    """
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    resume = {"implementer": "ready", "reviewer": "implementing"}
    goal.require_state(
        {"implementing"} if args.role == "implementer" else {"reviewing"},
        f"retry a {args.role} dispatch",
    )
    job = find_job(goal, args.round, args.role)
    require_quiescent(goal)
    if job.get("transport_status") not in {"completed", "failed", "cancelled", "timeout"}:
        fail("cannot retry an active or unknown attempt; verify the old worker stopped first")
    # The transport refuses a result path that already exists (anti-stale).
    # Set a failed attempt's artifact aside at the goal root so the redispatch
    # is not blocked and the evidence survives.
    sub = "deliveries" if args.role == "implementer" else "reviews"
    artifact = goal.dir / sub / f"{args.round}.json"
    aside = None
    if artifact.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        aside = goal.dir / f"{args.round}-{args.role}-set-aside-{stamp}.json"
        artifact.rename(aside)
    worker_artifact = Path(job.get("result_path", str(artifact)))
    if worker_artifact != artifact and worker_artifact.is_file():
        if worker_artifact.is_symlink() or not worker_artifact.resolve().is_relative_to(Path(job["workdir"])):
            fail("unsafe worker result path; inspect before retry")
        worker_artifact.rename(worker_artifact.with_name(f"{args.round}-set-aside-{uuid.uuid4().hex}.json"))
    entry = goal.round_entry(args.round)
    entry.setdefault("infra_retries", []).append(
        {
            "role": args.role,
            "note": args.note,
            "set_aside": aside.name if aside else None,
            "at": now_iso(),
        }
    )
    goal.set_state(resume[args.role])
    goal.save()
    return {
        "command": "retry",
        "goal_id": args.goal_id,
        "round_id": args.round,
        "role": args.role,
        "state": goal.state,
        "set_aside": aside.name if aside else None,
        "repairs_used": goal.data.get("repairs_used"),
        "errors": [],
    }


def ensure_runtime_ignore(workdir: Path) -> None:
    """Keep runtime output untracked without editing the repository ignore file."""
    runtime_dir = workdir / ".coordinator"
    safe_path(workdir, runtime_dir)
    runtime_dir.mkdir(exist_ok=True)
    ignore_file = runtime_dir / ".gitignore"
    safe_path(workdir, ignore_file)
    existing = ignore_file.read_text(encoding="utf-8") if ignore_file.exists() else ""
    if existing.splitlines()[-1:] == ["*"]:
        return
    separator = "\n" if existing and not existing.endswith("\n") else ""
    atomic_write(ignore_file, existing + separator + "*\n")


def cmd_archive(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    ensure_runtime_ignore(Path(args.workdir).resolve())
    sink = goal.dir.parent / "archives" / args.goal_id
    if sink.exists() and not args.force:
        fail(f"archive {sink} already exists; pass --force to overwrite")
    sink.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ("goal.json", "ledger.json", "constraints.md"):
        source = goal.dir / name
        if source.is_file():
            (sink / name).write_bytes(source.read_bytes())
            files.append(name)
    for sub in ("contracts", "deliveries", "reviews", "snapshots"):
        for source in sorted((goal.dir / sub).glob("*")):
            if source.is_file():
                target_dir = sink / sub
                target_dir.mkdir(exist_ok=True)
                (target_dir / source.name).write_bytes(source.read_bytes())
                files.append(f"{sub}/{source.name}")
    # At closeout withheld checks are declassified into the coordinator's
    # receipt archive. New goals keep these files only in host-private state.
    private_contracts = private_dir(args.goal_id) / "contracts"
    if private_contracts.is_dir():
        for source in sorted(private_contracts.glob("*")):
            if source.is_file():
                target_dir = sink / "contracts"
                target_dir.mkdir(exist_ok=True)
                (target_dir / source.name).write_bytes(source.read_bytes())
                archived_name = f"contracts/{source.name}"
                if archived_name not in files:
                    files.append(archived_name)
    meta = {
        "goal_id": args.goal_id,
        "state_at_archive": goal.state,
        "archived_at": now_iso(),
        "source": str(goal.dir),
        "files": files,
    }
    atomic_write(
        sink / "archive-meta.json", json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    return {
        "command": "archive",
        "goal_id": args.goal_id,
        "state": goal.state,
        "archived_to": str(sink),
        "files": files,
        "errors": [],
    }


def refresh_native_job(goal: Goal, job: dict) -> dict | None:
    """Inspect a reserved job without starting/resuming a provider turn."""
    if job.get("agent") != "agy" or not job.get("adapter"):
        return None
    state_dir = private_dir(goal.data["goal_id"]) / "transport"
    job["transport_status"] = "unknown"
    try:
        proc = subprocess.run([sys.executable, job["adapter"], "status", job["session_id"],
                               "--state-dir", str(state_dir), "--json"],
                              capture_output=True, text=True, timeout=10)
        native = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if not isinstance(native, dict) or native.get("job_id") != job["session_id"] or native.get("workdir") != job.get("workdir", str(goal.dir.parent.parent)):
        return None
    job["transport_status"] = native.get("status")
    job["activity"] = native.get("activity")
    job["conversation_id"] = native.get("thread_id")
    job["worker_exit_code"] = native.get("exit_code")
    return native


def refresh_job(goal: Goal, job: dict) -> dict | None:
    """Read runner facts, never infer liveness from provider prose."""
    if job.get("agent") == "agy":
        return refresh_native_job(goal, job)
    runner = job.get("transport_runner")
    if not runner:
        return None  # Legacy terminal receipts remain usable; unknown stays blocked.
    job["transport_status"] = "unknown"
    if not job.get("session_id") or not job.get("transport_state_dir"):
        return None
    try:
        proc = subprocess.run(["bash", runner, "status", job["session_id"],
                               "--state-dir", job["transport_state_dir"], "--json"],
                              capture_output=True, text=True, timeout=10)
        receipt = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if (proc.returncode or not isinstance(receipt, dict) or receipt.get("session_id") != job["session_id"]
            or receipt.get("agent") != job["agent"] or receipt.get("workdir") != job.get("workdir")):
        return None
    if receipt.get("status") in {"completed", "failed", "cancelled", "timeout"} and (
            type(receipt.get("worker_exit_code")) is not int or receipt.get("wait_timed_out")):
        return None
    job.update(transport_status=receipt.get("status"), worker_exit_code=receipt.get("worker_exit_code"),
               activity=receipt.get("activity"))
    return None  # Only native agy receipts carry structured_output.


def cmd_status(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    for job in goal.data.get("jobs", []):
        refresh_job(goal, job)
    return {
        "command": "status",
        "goal_id": args.goal_id,
        "state": goal.state,
        "current_round": goal.data.get("current_round"),
        "repairs_used": goal.data.get("repairs_used"),
        "repair_bound": goal.data.get("repair_bound"),
        "jobs": goal.data.get("jobs", []),
        "rounds": goal.ledger.get("rounds", {}),
        "errors": [],
    }


def transport_env(value: str) -> dict:
    # Repeated KEY=VALUE flags, passed through to the transport process.
    key, sep, val = value.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("transport env must be KEY=VALUE")
    return {key: val}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coordinator_goal.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, goal_id=True) -> None:
        p.add_argument("--workdir", default=".")
        if goal_id:
            p.add_argument("--goal-id", required=True)
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("init")
    common(p, goal_id=False)
    p.add_argument("--goal-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--mode", default="standard")
    p.add_argument("--start-revision")
    p.add_argument("--repair-bound", type=int, default=3)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("setup")
    common(p, goal_id=False)
    p.add_argument("--config")
    p.add_argument("--from-file", help="user-confirmed configuration JSON")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("workspace")
    p.add_argument("action", choices=["prepare", "status"])
    common(p)
    p.add_argument("--role", choices=["implementer", "reviewer"], default="implementer")
    p.add_argument("--round")
    p.add_argument("--base")
    p.add_argument("--config")
    p.add_argument("--include-untracked", action="append", default=[])
    p.set_defaults(func=cmd_workspace)

    p = sub.add_parser("freeze")
    common(p)
    p.add_argument("--round", required=True)
    p.add_argument("--role", choices=["implementer", "reviewer"], default="implementer")
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_freeze)

    p = sub.add_parser("dispatch")
    common(p)
    p.add_argument("--round", required=True)
    p.add_argument("--role", choices=["implementer", "reviewer"], required=True)
    p.add_argument("--agent", default="auto")
    p.add_argument("--config")
    p.add_argument("--model")
    p.add_argument("--effort")
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--transport-dir")
    p.add_argument("--transport-env", type=transport_env, action="append")
    p.set_defaults(func=cmd_dispatch)

    p = sub.add_parser("collect")
    common(p)
    p.add_argument("--round", required=True)
    p.add_argument("--role", choices=["implementer", "reviewer"], required=True)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("advance")
    common(p)
    p.add_argument(
        "--to",
        required=True,
        choices=["ready", "repairing", "completed", "human-gate", "blocked"],
    )
    p.add_argument("--note")
    p.set_defaults(func=cmd_advance)

    p = sub.add_parser("retry")
    common(p)
    p.add_argument("--round", required=True)
    p.add_argument("--role", choices=["implementer", "reviewer"], required=True)
    p.add_argument(
        "--note",
        required=True,
        help="the infrastructure cause being retried (recorded in the ledger)",
    )
    p.set_defaults(func=cmd_retry)

    p = sub.add_parser("archive")
    common(p)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("status")
    common(p)
    p.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "transport_env", None):
        merged: dict = {}
        for item in args.transport_env:
            merged.update(item)
        args.transport_env = merged
    try:
        directory = Path(args.workdir).resolve() / ".coordinator" / getattr(args, "goal_id", "")
        mutating = args.command not in {"status", "setup", "init"} and not (
            args.command == "workspace" and args.action == "status")
        if mutating and directory.is_dir():
            safe_path(Path(args.workdir).resolve(), directory)
            with goal_lock(directory):
                payload = args.func(args)
        else:
            payload = args.func(args)
    except (InputError, WorkspaceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INPUT
    except GuardError as error:
        print(f"guard: {error}", file=sys.stderr)
        return EXIT_GUARD
    emit(payload, args.json)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
