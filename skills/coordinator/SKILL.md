---
name: coordinator
description: The coordinating agent's control-plane playbook, from raw idea to verified delivery. Route by complexity - handle simple work directly, grill vague requirements into a sharp plan (references/grilling.md), freeze complex single-round work into a self-contained task brief (任务书, references/brief-authoring.md), and run super-complex multi-round work as a verified loop with independent acceptance evidence. Use when coordinating coding agents, keeping implementation and acceptance separate, stress-testing a plan (grill), writing a /goal task brief, or running a plan/implement/review loop; do not use for a simple single-agent edit, unapproved provider spending, or work without a verifiable outcome.
---

# Coordinator

Load this Skill in the coordinating agent (管控者). Its job is to keep the main
direction from drifting: understand what the user actually wants, then choose
the smallest mechanism that guarantees the direction holds. Executors and
reviewers never load this Skill — they receive frozen prompts from the
coordinator and nothing else.

## Route by complexity

| Tier | The work is… | The mechanism |
|---|---|---|
| **0** | Simple edit, quick question, read-only lookup | Handle it directly. Do not load anything from this Skill. |
| **1** | Direction or requirements still vague | Interview the user per [grilling.md](references/grilling.md) until the design-tree frontier is empty; capture CONTEXT.md + ADRs as you go. |
| **2** | Clear direction, complex but single-round deliverable | Freeze it into a self-contained task brief per [brief-authoring.md](references/brief-authoring.md) (≤4000 chars for `/goal`), dispatch through a transport, verify against the brief's checks. |
| **3** | Super-complex, multi-round, or acceptance must be independent of the implementer | Run the verified loop below: durable target (constraint set + plan ledger), frozen contracts, withheld checks, evidence-gated acceptance. |

Escalate tiers when evidence demands it: a Tier 1 interview that surfaces real
risk feeds Tier 2/3; a Tier 2 brief that bounces more than the declared repair
bound becomes a Tier 3 goal. Tiers 1 and 2 are modules of the same control
plane as Tier 3, not separate products — a brief's 明卷/暗卷 are the loop's
open/withheld checks.

## Vocabulary

| Term | Same thing elsewhere | Meaning |
|---|---|---|
| coordinator | 管理者 / 管控者 | The agent holding this playbook; owns decisions |
| user | 领导 | The human; owns direction and external-effect authorization |
| implementer | 执行者 | The role carrying out a frozen contract |
| reviewer | 验收官 / acceptance agent | The independent evidence role |
| goal | run（旧称，已退役） | One objective with direction, bounds, and verifiable completion; tracked in `.coordinator/<goal-id>/` |
| round | 轮 | One contract → candidate → verdict cycle inside a goal |
| session / job | — | A transport-level worker process (coding-agent says session, codex_run says job) |
| archive | 回执包 | Terminal receipt copy under `skills/coordinator/goals/`, gitignored |

## The verified loop (Tier 3)

This Skill defines the control plane: scope, frozen
contracts, acceptance evidence, durable state, and stop decisions. A native
subagent API or host-provided CLI adapter transports role-specific contracts and
returns artifacts; it does not decide what should pass. Give implementers and
reviewers only the context their roles require, not the coordinator's full
context.

For a goal that spans rounds or coordinator contexts, read and apply
[the runtime contract](references/runtime-contract.md). It defines the lifecycle,
portable state, transport boundary, and role envelopes. The coordinator is the
only role allowed to advance that lifecycle.

Optimize for verified work completed, not for tokens consumed. Separate the role
that decides from the role that executes, put ground truth outside the
implementer, and treat every worker report as a claim until evidence confirms it.

One round is: measure the ground and disclose the calls made on the user's
behalf, freeze a contract and dispatch it, judge the result against evidence the
implementer never saw, then advance the plan or issue a narrow repair. Direction
is held by the constraint set and the plan ledger in the repository, not by the
coordinator's attention.

## Set up once per host

Which CLI plays which role is a host fact, not part of the method. On first use
in an environment, inspect installed CLIs and existing host configuration first,
then keep resolved answers in the host environment rather than in this Skill:

- which CLI coordinates, which implements, and which reviews;
- which of them may write, commit, or affect anything outside the worktree;
- which is cheapest and fastest, and which is strongest.

Verify observable capabilities with the CLI's local `--help`. Ask one
consolidated question only for unresolved role choices or permissions that
materially affect the goal. A minimal smoke on a network-backed CLI can reach
the provider and spend real quota before any task has been authorized, so
disclose that cost and get the user's go-ahead before running it — never run a
provider-reaching smoke silently during host setup. Read the matching
provider reference in the `coding-agent` Skill for per-CLI facts rather than
restating them here, and re-confirm after a CLI upgrade. This Skill depends on
those provider references: a standalone install must copy the `coding-agent`
Skill directory alongside this one. When the transport is a different
monitored runner with no matching reference here, fall back to that runner's
own local `--help` and documentation instead of skipping the confirmation.

Confirm that the selected transport can dispatch an exact contract, preserve the
chosen workspace and permissions, report terminal state, expose logs and the
declared result artifact, and cancel a job. Record optional capabilities such as
resume or usage reporting; do not require them from every host.

Do not ask for subscription balances. No provider exposes reliable telemetry, and
the usage reported by one call describes that call alone. When a subscription
should be favored or avoided for a while, take it as a run-time instruction.

## Establish the goal

Resolve by inspection or collect only when not observable:

- the task, repository, starting revision, scope, and external side effects;
- the required quality floor and machine-verifiable completion signals;
- whether the user authorized multi-provider execution for this task.

Measure before asking. Run the commands, read the code, and record real baseline
numbers, because a command named in a document may not exist, a lint step may be
a placeholder that always passes, and a stated capability may not match the
installed one.

For judgment calls, use a safe reversible default when it preserves the stated
quality floor and scope. Ask only when a missing choice would materially change
the outcome and measurement cannot settle it; in this Skill the choices worth a
question are direction, acceptance strictness, and risk. Consolidate into one
round, and ask again only when new evidence invalidates the
authorization or assumption being relied on.

Otherwise decide, and disclose. List every call made on the user's behalf in one
labeled section of the contract, and mark anything unverified as an assumption.
Deciding silently takes authority the user did not give; deciding in the open
gives them a cheap veto, which is why this section belongs where they will
actually look. Answer these once per objective and keep them in the constraint
set, not in each round's prompt.

## Choose a mode and route roles

Read [the operating modes](references/modes.md), then select the smallest mode
that meets the quality floor.

Keep roles abstract: coordinator, implementer, and reviewer. Assign from the
host's setup rather than permanently binding a vendor to a role, and when an
eligible alternative exists, do not let the implementer approve its own work.

Route by cost, which is observable, rather than by remaining balance, which is
not:

- spend the strongest and most expensive context on what decides the outcome:
  understanding the problem, freezing the contract, writing withheld checks, and
  adjudicating disputed evidence;
- give high-frequency iteration to the cheapest provider that can carry it. The
  compile, test, and fix loop consumes the most tokens per unit of progress and
  gains the least from a stronger model;
- prefer a reviewer from a different engine family, so a shared blind spot is
  less likely;
- budget the reviewer as an executor rather than an author. Its brief is short
  because it points at a judge and its expected values, but the review itself
  reruns the suite and builds its own harness, so it costs far more than reading
  a diff.

For provider execution, use a host-provided adapter whose local help and smoke
behavior have been verified. Compatible hosts may use `coding-agent` or
another monitored runner, but none is bundled here. Do not
silently switch providers after an infrastructure failure.

## Dispatch useful work

For implementation or substantial investigation, write a frozen task contract
using [the task contract](references/task-contract.md). Give each worker only the
context needed for its role. The brief format in
[brief-authoring.md](references/brief-authoring.md) (open checks in the brief,
withheld checks kept by the coordinator) matches this protocol's contract
split and is the usual way to author a Tier 2/3 dispatch.

Across a goal that must survive context loss, process restart, or handoff, keep
the invariants, remaining work, and contracts in the repository rather than in
each prompt, and open every dispatch with a read-back of them. Do not create
durable state files for a short goal that can complete in the current
session. Read
[durable state between rounds](references/durable-state.md). A contract is
bounded while the invariants accumulate, so restating them each round costs more
of that bound and leaves the selection unchecked in the coordinator's context.
Use the public and private state split in
[the runtime contract](references/runtime-contract.md); never put withheld checks
or credentials in the role-visible goal directory.

Before dispatching, establish what will decide the outcome independently of the
worker's own report: an external judge where a reference exists, and numeric
gates that may only move up. Read
[ground truth and gates](references/ground-truth.md).

When an authoritative expectation can expose a plausible-but-wrong result, keep
that check in the reviewer contract rather than the implementer's prompt. Scale
withheld checks with risk instead of manufacturing guessed expectations merely
to satisfy the protocol. Select useful shapes from
[the standing withheld checks](references/withheld-checks.md), and use the same
list to preempt common failures in the task contract.

Every provider call must produce at least one of:

- a code or configuration diff;
- a rerunnable test, benchmark, or failure reproduction;
- an evidence-backed decision that eliminates an option;
- an independent review verdict with file or command evidence;
- maintained documentation tied to current repository behavior.

A call that cannot produce one of these does not belong in the goal. Idle capacity
costs nothing, while a round spent on work nobody needed costs the coordinator's
attention, which is the resource that actually runs short.

## Mechanism: coordinator_goal.py

`scripts/coordinator_goal.py` executes the state machine from
[the runtime contract](references/runtime-contract.md) so the coordinator does
not relay jobs or keep books by hand. It does three things and no more:

- **Bookkeeping** — `init` scaffolds `.coordinator/<goal-id>/` (`goal.json`,
  `ledger.json`, `constraints.md`, contract/delivery/review directories);
  `status` reports current state.
- **Guarded transitions** — `freeze` (establishing/repairing → ready),
  `dispatch` (drives the `coding-agent` transport; ready → implementing →
  reviewing), and `advance` (coordinator-driven moves) refuse illegal
  transitions. The repair bound is enforced mechanically: when it is
  exhausted, the only legal move is `blocked`.
- **Mechanical envelope validation** — `collect` checks the implementation
  and review envelopes against their contract shapes. A missing or malformed
  artifact is recorded as an **infrastructure failure**, never as an
  implementation rejection.

It never adjudicates. `collect` reports facts (verdict, mechanical go shape,
infrastructure failures); the coordinator weighs them and calls `advance`
explicitly. A typical round:

```bash
SKILL_DIR=/path/to/coordinator
cd /path/to/worktree

python3 "$SKILL_DIR/scripts/coordinator_goal.py" init --goal-id goal-1 \
  --objective "..." --mode standard --repair-bound 3 --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" freeze --goal-id goal-1 \
  --round round-1 --contract /path/to/task-brief.md --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" freeze --goal-id goal-1 \
  --round round-1 --role reviewer --contract /path/to/review-brief.md --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" dispatch --goal-id goal-1 \
  --round round-1 --role implementer --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" collect --goal-id goal-1 \
  --round round-1 --role implementer --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" dispatch --goal-id goal-1 \
  --round round-1 --role reviewer --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" collect --goal-id goal-1 \
  --round round-1 --role reviewer --json
python3 "$SKILL_DIR/scripts/coordinator_goal.py" advance --goal-id goal-1 \
  --to completed --note "gate reproduced" --json
```

The transport defaults to the sibling `coding-agent` Skill; override with
`--transport-dir` or `CODING_AGENT_DIR`. Withheld checks and raw transport
logs still live in host-private state, outside the repository. When a goal
ends, `archive` copies the receipt bundle to `skills/coordinator/goals/<goal-id>/`
(gitignored) — the long-term, traceable record; the worktree
`.coordinator/<goal-id>/` is per-run working state.

## Verify and stop

Use [the review contract](references/review-contract.md). The controller, not a
worker's prose, decides whether evidence meets the gate.

- Treat authentication, sandbox, timeout, malformed envelope, and missing-tool
  failures as infrastructure failures, not implementation failures.
- Keep the transport envelope, implementation envelope, and review verdict
  separate. Process success proves neither a valid delivery nor acceptance.
- Record open and withheld check results separately, so the value of withholding
  stays measurable instead of assumed.
- Repair a rejected candidate with a narrow fix contract that carries the
  previous gates forward, not by reissuing the original task.
- Declare a retry, time, or cost bound proportional to the run's risk before
  dispatch. This is the run-level bound; it caps contract reissues, not the
  worker's own inner-loop retries inside one dispatch. When a blocker recurs,
  use the evidence to change contract, provider,
  or approach; stop at the declared bound instead of applying a universal retry
  count.
- Do not merge, push, deploy, or mutate external systems unless the user has
  authorized that effect.
- Record provider, role, start revision, output artifact, commands, verdict,
  elapsed time, and usage when available. This receipt is the input to later
  evaluation; it is not proof that the method improved.

Read [methodology and limits](references/methodology.md) when changing this
protocol, and [evidence provenance](references/evidence.md) when evaluating how
strongly its current rules are supported.
