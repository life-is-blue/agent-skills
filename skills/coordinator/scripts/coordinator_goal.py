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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path, what: str) -> dict:
    if not path.is_file():
        fail(f"{what} not found at {path}; use `init` first")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        fail(f"{what} at {path} is malformed; inspect it by hand")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Dispatch appends the role's envelope schema as the FINAL prompt segment.
# Hard-won lesson (goal inv-recon-74 / verdict-taxonomy): a schema embedded in
# a long contract loses to the worker's attention budget — the worker improvises
# field names, three malformed envelopes in a row. The tail below is injected
# by the runner itself so it is identical and last on every dispatch, no matter
# what the contract says or what other schemas are visible nearby.
ENVELOPE_TAILS = {
    "implementer": """
═══ 交付信封 schema（机械校验，优先级高于上文一切格式暗示）═══
把你的交付 JSON 写到合同指定的 result 路径。你**必须**提供的字段：
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
把裁决 JSON 写到合同指定的 review 路径。你**必须**提供的字段：
{"verdict":"go"或"no-go",
"candidate_revision":"...",
"checks":[{"id":"...","kind":"open"或"withheld","required":true,
"passed":true或false,"evidence":"命令+结果"},...],
"blockers":[...],"spec_uncertainties":[...],"infrastructure_errors":[...]}
登记字段（schema_version/role/round_id/start_revision）由 runner 自动补齐，
你不用写；若写，必须与事实完全一致。verdict 只有 go|no-go。
""",
}


def build_dispatch_prompt(role: str, contract: Path, round_id: str) -> str:
    return (
        contract.read_text(encoding="utf-8")
        + ENVELOPE_TAILS[role].replace("<本轮 id>", round_id)
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
    goal_dir = workdir / ".coordinator" / args.goal_id
    if goal_dir.exists():
        fail(f"goal directory {goal_dir} already exists; pick a new goal-id")
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
        goal.require_state({"establishing", "repairing"}, "freeze a contract")
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
    target = goal.dir / "contracts" / f"{args.round}{suffix}.md"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    entry = goal.round_entry(args.round)
    key = "review_contract" if args.role == "reviewer" else "contract"
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


def cmd_dispatch(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    workdir = Path(args.workdir).resolve()
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
    contract = goal.dir / "contracts" / f"{args.round}{suffix}.md"
    if not contract.is_file():
        fail(f"contract {contract} not found; freeze it first")

    runner = resolve_transport_dir(args.transport_dir)
    # The prompt is contract + runner-injected envelope schema tail (see
    # ENVELOPE_TAILS). Materialize the combined prompt for the transport.
    prompt_file = goal.dir / "contracts" / f"{args.round}{suffix}.prompt.md"
    atomic_write(
        prompt_file, build_dispatch_prompt(args.role, contract, args.round)
    )
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
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=args.timeout,
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

    job = {
        "round_id": args.round,
        "role": args.role,
        "session_id": envelope.get("session_id"),
        "agent": envelope.get("agent", args.agent),
        "dispatched_at": now_iso(),
        "transport_status": envelope.get("status"),
        "worker_exit_code": envelope.get("worker_exit_code"),
        "result_artifact": envelope.get("result_artifact", {}).get("status"),
    }
    goal.data.setdefault("jobs", []).append(job)
    goal.set_state("implementing" if args.role == "implementer" else "reviewing")
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
    rel = (
        f"deliveries/{args.round}.json"
        if args.role == "implementer"
        else f"reviews/{args.round}.json"
    )
    artifact = goal.dir / rel
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


def cmd_archive(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
    skill_dir = Path(__file__).resolve().parents[1]
    sink = skill_dir / "goals" / args.goal_id
    if sink.exists() and not args.force:
        fail(f"archive {sink} already exists; pass --force to overwrite")
    sink.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ("goal.json", "ledger.json", "constraints.md"):
        source = goal.dir / name
        if source.is_file():
            (sink / name).write_bytes(source.read_bytes())
            files.append(name)
    for sub in ("contracts", "deliveries", "reviews"):
        for source in sorted((goal.dir / sub).glob("*")):
            if source.is_file():
                target_dir = sink / sub
                target_dir.mkdir(exist_ok=True)
                (target_dir / source.name).write_bytes(source.read_bytes())
                files.append(f"{sub}/{source.name}")
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


def cmd_status(args: argparse.Namespace) -> dict:
    goal = Goal(Path(args.workdir).resolve(), args.goal_id)
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
        payload = args.func(args)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INPUT
    except GuardError as error:
        print(f"guard: {error}", file=sys.stderr)
        return EXIT_GUARD
    emit(payload, args.json)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
