---
name: verified-dev-loop
description: Coordinate substantial software development as repeated rounds that freeze delegated work, collect evidence, and end at an acceptance gate. Use when the user asks a primary agent to coordinate coding agents, keep implementation and acceptance separate, or run a plan/implement/review loop; do not use for a simple single-agent edit, unapproved provider spending, or work without a verifiable outcome.
---

# Verified Dev Loop

Load this Skill in the coordinator. It defines the control plane: scope, frozen
contracts, acceptance evidence, durable state, and stop decisions. A native
subagent API or host-provided CLI adapter transports role-specific contracts and
returns artifacts; it does not decide what should pass. Give implementers and
reviewers only the context their roles require, not the coordinator's full
context.

For a run that spans rounds or coordinator contexts, read and apply
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
in an environment, ask the user once, then keep the answer in the host
environment rather than in this Skill:

- which CLI coordinates, which implements, and which reviews;
- which of them may write, commit, or affect anything outside the worktree;
- which is cheapest and fastest, and which is strongest.

Confirm each answer instead of accepting it: run the CLI's local `--help` and one
minimal smoke, because a documented capability and the installed behavior diverge
often enough to matter. Read the matching provider reference in the
`coding-agent` Skill for per-CLI facts rather than restating them here, and
re-confirm after a CLI upgrade.

Confirm that the selected transport can dispatch an exact contract, preserve the
chosen workspace and permissions, report terminal state, expose logs and the
declared result artifact, and cancel a job. Record optional capabilities such as
resume or usage reporting; do not require them from every host.

Do not ask for subscription balances. No provider exposes reliable telemetry, and
the usage reported by one call describes that call alone. When a subscription
should be favored or avoided for a while, take it as a run-time instruction.

## Establish the run

Collect or confirm:

- the task, repository, starting revision, scope, and external side effects;
- the required quality floor and machine-verifiable completion signals;
- whether the user authorized a multi-provider run for this task.

Measure before asking. Run the commands, read the code, and record real baseline
numbers, because a command named in a document may not exist, a lint step may be
a placeholder that always passes, and a stated capability may not match the
installed one. Anything a measurement can settle is not a question for the user.

What measurement cannot settle is usually a judgment call: a direction tradeoff,
how strict acceptance should be, how much risk is acceptable. Ask about those
while the user is present, giving each question a short set of options and a
recommendation. Consolidate them into one round by default, but ask again when
new evidence exposes a decision or invalidates an earlier assumption.

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
behavior have been verified. Compatible hosts may use `coding-agent`,
`codex-delegate`, or another monitored runner, but none is bundled here. Do not
silently switch providers after an infrastructure failure.

## Dispatch useful work

For implementation or substantial investigation, write a frozen task contract
using [the task contract](references/task-contract.md). Give each worker only the
context needed for its role.

Across a multi-round run, keep the invariants, the remaining plan, and the
contracts themselves in the repository rather than in each prompt, and open every
dispatch with a read-back of them. Read
[durable state between rounds](references/durable-state.md). A contract is
bounded while the invariants accumulate, so restating them each round costs more
of that bound and leaves the selection unchecked in the coordinator's context.
Use the public and private state split in
[the runtime contract](references/runtime-contract.md); never put withheld checks
or credentials in the role-visible run directory.

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

A call that cannot produce one of these does not belong in the run. Idle capacity
costs nothing, while a round spent on work nobody needed costs the coordinator's
attention, which is the resource that actually runs short.

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
  dispatch. When a blocker recurs, use the evidence to change contract, provider,
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
