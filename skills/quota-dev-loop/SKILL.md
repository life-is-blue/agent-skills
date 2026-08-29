---
name: quota-dev-loop
description: Route substantial software development across multiple subscribed coding CLIs so each call produces independently verified work, separating plan, implementation, and acceptance across providers. Use when the user asks to coordinate heterogeneous coding agents, get more out of several AI subscriptions, or run a plan/implement/review loop with independent acceptance; do not use for a simple single-agent edit, unapproved provider spending, or work without a verifiable outcome.
---

# Quota Dev Loop

Optimize for verified work completed, not for tokens consumed. Separate the role
that decides from the role that executes, put ground truth outside the
implementer, and treat every worker report as a claim until evidence confirms it.

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

Do not ask for subscription balances. No provider exposes reliable telemetry, and
the usage reported by one call describes that call alone. When a subscription
should be favored or avoided for a while, take it as a run-time instruction.

## Establish the run

Collect or confirm:

- the task, repository, starting revision, scope, and external side effects;
- the required quality floor and machine-verifiable completion signals;
- whether the user authorized a multi-provider run for this task.

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
- budget the reviewer as a first-class consumer of capacity. A review brief
  carries expected values, reproduction steps, and withheld checks the
  implementer never received, so it can cost several times the contract it
  judges; it is not a quick look at a diff.

For provider execution, use a host-provided adapter whose local help and smoke
behavior have been verified. Compatible hosts may use `coding-agent`,
`codex-delegate`, or another monitored runner, but none is bundled here. Do not
silently switch providers after an infrastructure failure.

## Dispatch useful work

For implementation or substantial investigation, write a frozen task contract
using [the task contract](references/task-contract.md). Give each worker only the
context needed for its role.

Before dispatching, establish what will decide the outcome independently of the
worker's own report: an external judge where a reference exists, and numeric
gates that may only move up. Read
[ground truth and gates](references/ground-truth.md).

Keep the checks that would reveal a plausible-but-wrong result in the reviewer
contract, never in the implementer's prompt; a worker satisfies what it can see,
so visible checks alone mostly confirm what the contract already demanded. Select
them from [the standing withheld checks](references/withheld-checks.md) instead of
composing them from scratch, and use the same list to preempt the common failures
in the contract, which is cheaper than catching them in review.

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
- Record open and withheld check results separately, so the value of withholding
  stays measurable instead of assumed.
- Repair a rejected candidate with a narrow fix contract that carries the
  previous gates forward, not by reissuing the original task.
- After the same substantive blocker fails twice, change provider or approach.
  After a third failure, stop and surface the evidence instead of spending more
  capacity blindly.
- Do not merge, push, deploy, or mutate external systems unless the user has
  authorized that effect.
- Record provider, role, start revision, output artifact, commands, verdict,
  elapsed time, and usage when available. This receipt is the input to later
  evaluation; it is not proof that the method improved.

Read [methodology and limits](references/methodology.md) when changing this
protocol, and [evidence provenance](references/evidence.md) when evaluating how
strongly its current rules are supported.
