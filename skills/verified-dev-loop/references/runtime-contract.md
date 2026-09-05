# Runtime contract

Use this contract when a run must survive a coordinator context reset or move
between compatible hosts. The coordinator owns the state machine. A transport
reports execution facts; an implementer reports a candidate; a reviewer reports
evidence. None of those reports advances the run by itself.

## Coordinator states

Record one of these states in `run.json`:

- `establishing`: measure the baseline, settle decisions, and choose a mode.
- `ready`: the next frozen contract and its acceptance evidence are complete.
- `implementing`: an implementation or narrow-repair dispatch is active.
- `reviewing`: the candidate is frozen and an acceptance dispatch is active.
- `repairing`: review rejected the candidate and the next contract is bounded to
  the unresolved findings.
- `human-gate`: progress requires a user decision or authorization.
- `blocked`: the declared retry or cost bound is exhausted, or no eligible
  transport can continue.
- `completed`: the controller reproduced the final gate and closed the ledger.

The ordinary path is `establishing -> ready -> implementing -> reviewing`, then
either `ready` for the next planned dispatch, `repairing`, or `completed`.
Infrastructure failure leaves the candidate undecided; it does not become an
implementation rejection. Record the failure and retry or reroute only within
the bound declared for this run.

## Public run directory

Unless the repository names another runtime-artifact location, use
`.verified-dev-loop/<run-id>/` in the worktree:

```text
run.json
constraints.md
ledger.json
contracts/<round-id>.md
deliveries/<round-id>.json
reviews/<round-id>.json
```

`run.json` records `schema_version`, `run_id`, objective, mode, state, starting
revision, current round, chosen transport, and update time. `ledger.json` records
each bounded dispatch, dependencies, state, and the gates it established. Keep
both as current state, not an event log.

These files are visible to roles that can read the worktree. Do not automatically
commit them or edit `.gitignore`; follow the target repository's runtime-artifact
policy. Put withheld checks and raw transport logs in the host state directory,
keyed by the same run ID. Never copy credentials into either location.

## Transport conformance

A compatible transport can:

1. dispatch the exact contract text or repository path to a named role;
2. preserve the workspace and permission boundary chosen by the coordinator;
3. return a stable job identity and distinguish running, terminal, timeout,
   cancellation, and lost-worker states;
4. expose raw logs and the declared result artifact; and
5. cancel an active job without treating cancellation as acceptance.

Resume, background notifications, token usage, and provider-native structured
output are optional capabilities. Probe the installed transport with local help
and a minimal smoke, record its capabilities in `run.json`, and do not silently
change provider or permissions after dispatch.

Record whether the host preserves detached processes between tool calls. Use a
synchronous transport when it reaps them; use background dispatch only after a
smoke proves that its job identity remains live in the next coordinator call.
Routing and reroute facts belong here, not in the implementer's work contract.

The transport envelope must keep process outcome separate from result-artifact
outcome. At minimum it carries a schema version, job or session ID, provider,
status, worker exit code, worktree, timestamps, log location, result-artifact
path/status/hash, and structured transport errors. A zero worker exit with a
missing required artifact is a transport failure, not an accepted delivery.

## Implementation envelope

Require the implementer to write a JSON equivalent of:

```json
{
  "schema_version": 1,
  "role": "implementer",
  "status": "completed",
  "round_id": "round-1",
  "start_revision": "...",
  "candidate_revision": "...",
  "changed_files": ["src/example.py"],
  "commands": [
    {"command": "python3 -m pytest -q", "exit_code": 0}
  ],
  "unresolved": [],
  "summary": "..."
}
```

`status` is `completed` or `blocked`. The envelope is a claim: the coordinator
checks the revision, diff, files, and commands before starting review. A missing
or malformed envelope is an infrastructure failure. It is never reconstructed
from optimistic prose in the log.

The reviewer writes the public verdict envelope defined in
[the review contract](review-contract.md), while full withheld inputs and outputs
remain in private host state. Only after that verdict and the controller's own
repository gate agree may the controller advance the ledger or mark the run
complete.
