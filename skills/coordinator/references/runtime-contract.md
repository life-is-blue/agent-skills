# Runtime contract

Use this contract when a goal must survive a coordinator context reset or move
between compatible hosts. The coordinator owns the state machine. A transport
reports execution facts; an implementer reports a candidate; a reviewer reports
evidence. None of those reports advances the goal by itself.

## Configuration gate

`dispatch` requires configuration before accessing a goal or launching a
provider. Use `.coordinator/config.json` by default; `--config FILE` overrides
`COORDINATOR_CONFIG`, which overrides that default. An explicit config is a whole
configuration, not a merged project overlay. No configuration is written to a
user directory automatically. The default file is covered by the runtime ignore.

First run `coordinator_goal.py setup --workdir REPO --json`: it returns a preview
and confirmation requirements, without creating files or calling a provider.
Recommend Codex `gpt-5.6-luna` with `high`, agy Gemini Flash 3.8 or newer Flash
with `high`, and TClaude DeepSeek Flash v4 or newer Flash (effort configurable).
Recommend Codex `gpt-5.6-sol` with `medium` for review. Confirm the actual ID during
setup rather than inheriting a CLI default. This is a capability preference,
not a benchmark or an enforced model-quality floor.
These are user-selected baselines, not verified claims about model availability.
Resolve actual IDs from local catalogs/cache or an authorized metadata query;
do not save family names, ranges or silently track future versions. Do not enable
an extra paid Fast service tier implicitly.

Setup recommends enabling local milestone commits; confirm this authorization
alongside role/model choices, then write an input JSON and run
`setup --from-file FILE --workdir REPO --json`. The script validates the schema
and local help surfaces before saving. It refuses to overwrite existing config;
review subsequent edits explicitly. Example confirmed config shape:

```json
{
  "schema_version": 1,
  "execution": {"local_commits": true},
  "implementer": [
    {"agent": "codex", "model": "gpt-5.6-luna", "effort": "high"}
  ],
  "reviewer": [
    {"agent": "codex", "model": "gpt-5.6-sol", "effort": "medium"}
  ]
}
```

Top-level fields are schema version, role arrays and optional `execution`;
`execution` accepts only boolean `local_commits`. Missing authorization in an old
config means false, never an implicit upgrade. Candidate fields are `agent`,
concrete `model`, and optional `effort`. The configured model
adapters currently support Codex, agy, Claude Code and TClaude; other plain-log
providers remain usable directly, not through this model gate. No credentials,
permission bypass or spending grants belong in this config. Local commit consent
is limited to the task's isolated implementer worktree; it does not override
higher-priority host rules or narrower task restrictions.

Dispatch records the effective `local_commits` authorization and injects its
boundary for every implementation adapter, including agy. Reviewers and non-Git
roots never inherit it. Within an authorized worktree, disclose the local commit
immediately before invoking it, stage explicit task files and commit one coherent,
reviewable, independently revertible change after relevant checks pass. Include
its tests and necessary docs, and explain the intent in the commit message.
For larger tasks, consider checkpoints every
30–60 minutes and before handoff or round completion; this is worker guidance,
not a mechanically enforced timer or an obligation to commit incomplete work.
A blocker alone does not trigger a commit. Exclude runtime output, credentials
and unrelated changes. Push, merge, history rewrite, changes to other worktrees'
branches or tags, and cleanup remain separately gated. A commit does not establish
final acceptance.

`auto` selects the first installed configured candidate with an installed
distinct provider/model review option. Review prefers installed different-provider
candidates, preserving configured order within each group; when none qualifies,
it permits a different model on the same provider, such as Codex Luna → Sol.
Explicit `--agent` restricts that list;
`--model` and `--effort` override the selected settings but cannot bypass setup
or validation. Unsupported flags/efforts block before launch, not silently fall
back. Overrides are checked against the actual implementer job, not just the
configured implementation defaults. The same provider/model pair is refused,
regardless of effort; legacy jobs with no model cannot use same-provider review.
Different model IDs can be aliases and do not prove engine diversity or independence.
No eligible reviewer blocks dispatch, never relaxes acceptance. Review starts a
separate task context, not a resumed implementation conversation. This routing
does not prove enforced read-only execution:
choose independent engines and preserve the existing review workspace boundary.

Each job records resolved provider/model/effort and SHA-256 of the loaded config
serialized with sorted keys. CLI help checks prove parameter surfaces, not actual
account access, latency or model quality. Live smoke/benchmark and writes to an
explicit outside-workspace config destination still need applicable authorization.

## Managed workspaces

Requires Git, Python 3 and a POSIX host (the local controller lock uses `flock`).
Run control commands with `--workdir REPO` from the checkout containing the shared
Git metadata. Keep config and the goal ledger there, not inside worker checkouts.

After `init`, run `workspace prepare --goal-id GOAL --role implementer --json`.
It resolves the goal's starting commit, creates a detached worktree under
`.coordinator/worktrees/GOAL/implementer/`, generates its runtime ignore, and
registers its absolute path and Git identity in `goal.json`. `--base REF` must
resolve to the goal's starting SHA. No fetch, commit, branch reset, dependency
installation or ignored-file copy occurs. Uncommitted control-checkout changes
are not carried into the fresh checkout. Use trusted repositories/refs only;
Git checkout and staging can invoke configured filters, so untrusted inputs need
an approved host sandbox, not this helper alone.

After implementation is terminal and collected, run `workspace prepare --role
reviewer --round ROUND --goal-id GOAL --json`. It freezes the implementer's actual
working files into a Git tree using a temporary index, leaving the implementer's
index and HEAD untouched, then materializes that tree in
`.coordinator/worktrees/GOAL/reviewer/ROUND/`. Binary content, executable bits,
tracked deletions and staged additions are preserved without making a commit.
Untracked nonignored files block freeze until each intended source is selected
with repeated `--include-untracked PATH`. Never select credentials; ignored
files such as `.env` are not copied. Resolve merge conflicts first. Submodules
require a host-managed review workspace. The snapshot's HEAD/tree IDs, selected
paths, SHA-256 and binary patch are saved under the goal's `snapshots/` and included
in its archive. A working-tree delivery is thereby reviewable, not mistaken for
its unchanged HEAD.

`workspace status` reports registered paths, Git identity validity, current HEAD
and changes without calling a provider. Repeated prepare verifies and reuses a
registered checkout without resetting it. Unregistered existing paths, symlinked
managed paths, changed Git identity, mismatching bases, active/unknown workers
and concurrent mutating controller operations are refused. Creation failures
leave files and Git registration intact for inspection; no automatic cleanup,
unlock, deletion or guessed re-adoption. Controller locks release when their
process exits; status remains available while dispatch holds the lock.

`dispatch` loads config from the control root, selects the registered role/round
workspace and rechecks identity before launching. Review also rechecks both
the source candidate and review checkout against the frozen tree. Dispatch creates
role-visible copies of constraints/ledger; implementers also receive
their open contract. These are read-back projections, not authority to update the
control ledger. Private reviewer contracts/prompts are never projected there.
Results are written inside the worker root, then copied and envelope-validated by `collect`
in the control goal directory. Retry sets aside both copies rather than allowing
stale output to satisfy a new attempt. A modified review checkout is not reset
for retry; inspect it and use the host recovery boundary if it no longer matches
the candidate. Manual repair must not change a frozen candidate under review.

An existing externally managed linked worktree remains a compatible execution
root when no managed workspaces are registered; the primary Git checkout and
Git identity environment redirects are refused. Non-Git transports retain the
protocol-only path and must establish their own host workspace boundary (Codex
still requires Git). Worktrees share Git metadata and are not permission or
withheld-input isolation. Do not add the control checkout to a worker's writable
directories. Existing private-state location/authorization requirements remain.

Provider adaptation:

- Codex runs fresh `exec` in the registered root; the runner does not enable
  native `--worktree` or infer a resume thread. Review has a separate context.
- Claude Code runs print mode in that root, without native `--worktree`, tmux or
  background-session lifecycle. Native isolation checks must not be assumed
  merely because the runner changed cwd; preserve the authorized host sandbox.
- agy runs stream-json in that root. Its project selection is not a Git worktree
  identity. Fresh dispatch never passes `--continue`/`--conversation` or adds the
  control directory; explicit native resume remains a separately authorized turn.

Local CLI help and offline fake-provider fixtures establish this adapter path,
not live model access or complete provider-enforced isolation.

## Interrupted attempts

Dispatch records an unknown attempt before launching. A transport timeout or
malformed transport response leaves that attempt in place, not ready for retry.
`collect`, `retry` and workspace reuse refuse active/unknown attempts. New plain-log
jobs record the runner path and resolved state root; controller operations query
its local `status` and verify session/provider/worktree identity rather than trust
cached status or a log line. Missing/malformed status and identity mismatches stay
unknown. Legacy terminal receipts remain usable; legacy unknown jobs require
manual host recovery. Two live dispatches must never share an execution root;
the goal lock does not coordinate unrelated goals or raw CLI launches.
For agy, the reserved local
job ID is persisted before launch; `status` inspects its local state without a
provider call, and `collect` materializes a terminal structured delivery. The
job ID and provider conversation ID are different identities. Keep
`COORDINATOR_STATE_DIR` in an approved private location; agy raw output remains
there under the goal's `transport/jobs` directory.

Use the structured runner's status/logs/wait/cancel with that ID and state root
to recover. A missing manifest or `lost` status is unknown, not safely stopped.
Confirm process and any claimed detached/remote work have quiesced before a
new dispatch; explicit provider resume starts a new turn. Legacy plain-log
unknown attempts require inspecting their transport state and reconciling the
record; never change unknown to terminal from the worker's prose alone. Terminal
wrapper state does not prove claimed detached/remote work has stopped.

Plain-log status exposes log modification time and size as observations, not
heartbeats or proof of useful progress. Compare them across observations with
the process state and expected artifacts; a quiet log is not a dead worker.
Compare observations over a task-appropriate interval: native events, completed
tool results, process CPU-time delta, the claimed port and expected artifact
changes. Do not conflate text streaming with useful progress or automatically
kill from low CPU/file silence. Diagnose the claimed operation, retain evidence,
and enforce the declared execution/time/cost bound. Wait timeouts do not reset
execution bounds. A zero exit code or terminal result still requires envelope
validation and independent acceptance evidence.

## Coordinator states

Record one of these states in `goal.json`:

- `establishing`: measure the baseline, settle decisions, and choose a mode.
- `ready`: the next frozen contract and its acceptance evidence are complete.
- `implementing`: an implementation or narrow-repair dispatch is active.
- `reviewing`: the candidate is frozen and an acceptance dispatch is active.
- `repairing`: review rejected the candidate and the next contract is bounded to
  the unresolved findings.
- `human-gate`: progress requires a user decision or authorization.
- `blocked`: the declared retry or cost bound is exhausted, or no eligible
  transport can continue. A holding state awaiting a user decision, not a
  dead end: resume through `human-gate` (direct `blocked -> ready` is
  refused so the decision is always on record).
- `completed`: the controller reproduced the final gate and closed the ledger.

The ordinary path is `establishing -> ready -> implementing -> reviewing`, then
either `ready` for the next planned dispatch, `repairing`, or `completed`.
Infrastructure failure leaves the candidate undecided; it does not become an
implementation rejection. Record the failure and retry or reroute only within
the bound declared for this goal.

**Infrastructure retry is not a repair.** A transport-level failure (missing or
malformed envelope, stale-artifact refusal, dead worker) is retried with
`coordinator_goal.py retry --role <role> --note <cause>`, which sets the failed
artifact aside as evidence and returns to the role's dispatch state
(implementer → `ready`, reviewer → `implementing`) without consuming the repair
bound. The repair bound caps adjudicated rejections, not transport noise;
conflating the two makes `repairs_used` unreadable as a signal.

## Public goal directory

Unless the repository names another runtime-artifact location, use
`.coordinator/<goal-id>/` in the worktree:

```text
goal.json
constraints.md
ledger.json
contracts/<round-id>.md
deliveries/<round-id>.json
reviews/<round-id>.json
```

`goal.json` records `schema_version`, `goal_id`, objective, mode, state, starting
revision, current round, chosen transport, and update time. `ledger.json` records
each bounded dispatch, dependencies, state, and the gates it established. Keep
both as current state, not an event log.

These files are visible to roles that can read the worktree. `init` and `archive`
generate `.coordinator/.gitignore` with `*` to ignore the whole runtime directory,
including the ignore file itself. Existing contents are preserved and the rule
is appended only if needed. The repository's root ignore file and Git index are
not changed; already tracked files remain tracked and need a separately
authorized cleanup. Do not automatically commit runtime output. Put withheld
checks and raw transport logs in the host state directory,
keyed by the same goal ID. Never copy credentials into either location.

Reviewer contracts and their runner-materialized prompts use host-private state
under `$XDG_STATE_HOME/coordinator/<goal-id>/contracts/` (or
`~/.local/state/coordinator/` when XDG state is unset). Set
`COORDINATOR_STATE_DIR` to replace the coordinator state root. The public ledger
records only the reviewer contract SHA-256 and `private: true`, never its path.
Dispatch reads private state first and falls back to a legacy reviewer contract
in the public goal directory only when the private file is absent.

## Artifact lifecycle

The worktree goal directory is **per-goal working state**: it exists so roles can
read contracts and constraints while the goal is live, and it carries no
long-term obligation. When a goal reaches a terminal state, archive the receipt
bundle (`goal.json`, `ledger.json`, `constraints.md`, contracts, deliveries,
reviews) with `coordinator_goal.py archive`, which copies it to
`.coordinator/archives/<goal-id>/` in the target worktree, covered by the generated
ignore rule. It never writes the Skill installation directory. Existing archives
there are left in place, not migrated automatically. At closeout it also copies
private reviewer contracts and prompts into
the receipt bundle's `contracts/` directory, where withheld checks are
declassified. That archive is the long-term, traceable record and the raw material
for later skill evolution; the worktree copy may then be cleaned up by the
host's own policy. Goal receipts never enter the target repository's history
unless that repository deliberately chooses otherwise.

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
and a minimal smoke, record its capabilities in `goal.json`, and do not silently
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
repository gate agree may the controller advance the ledger or mark the goal
complete.
