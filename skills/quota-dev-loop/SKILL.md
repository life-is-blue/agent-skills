---
name: quota-dev-loop
description: Route substantial software development across multiple subscribed coding CLIs so expiring quota produces useful, independently verified work. Use when the user asks to maximize several AI subscriptions, coordinate heterogeneous coding agents, or run a quota-aware plan/implement/review loop; do not use for a simple single-agent edit, unapproved provider spending, or work without a verifiable outcome.
---

# Quota Dev Loop

Treat subscription quota as expiring capacity, not as a target for purposeless
token consumption. Preserve a quality floor first; among eligible providers,
prefer work that consumes the most urgent quota and produces a durable artifact,
decision, or independent proof.

## Establish the run

Collect or confirm:

- the task, repository, starting revision, scope, and external side effects;
- the required quality floor and machine-verifiable completion signals;
- available providers, readiness, write permissions, strengths, remaining quota,
  and reset time;
- whether the user authorized a multi-provider run for this task.

Do not infer remaining subscription quota from one run's token usage. When a
provider exposes no safe quota API, use a user-supplied normalized fraction or
the qualitative state `critical`, `high`, `normal`, `low`, or `unknown`. Keep
credentials and mutable quota state in the host environment, not this Skill.

## Choose a mode and route roles

Read [the operating modes](references/modes.md), then select the smallest mode
that both meets the quality floor and creates useful work for urgent quota.
Read [the quota routing protocol](references/quota-routing.md) before assigning
providers.

Keep roles abstract: coordinator, implementer, and reviewer. Assign providers
from current evidence rather than permanently binding a vendor to a role. When
an eligible alternative exists, do not let the implementer independently approve
its own work.

For provider execution, use a host-provided adapter whose local help and smoke
behavior have been verified. Compatible hosts may use `coding-agent`,
`codex-delegate`, `quota-router`, or another monitored runner, but none is
bundled here. Do not silently switch providers after an infrastructure failure.

## Dispatch useful work

For implementation or substantial investigation, write a frozen task contract
using [the task contract](references/task-contract.md). Give each worker only the
context needed for its role. Put independent checks in the reviewer contract,
not in the implementer's prompt.

Every provider call must produce at least one of:

- a code or configuration diff;
- a rerunnable test, benchmark, or failure reproduction;
- an evidence-backed decision that eliminates an option;
- an independent review verdict with file or command evidence;
- maintained documentation tied to current repository behavior.

When the main task cannot use urgent quota safely, draw from a prepared useful
backlog: regression gaps, adversarial tests, performance baselines, dependency
checks, documentation drift, technical-debt characterization, or alternative
design analysis. Never invent duplicate work solely to drain quota.

## Verify and stop

Use [the review contract](references/review-contract.md). The controller, not a
worker's prose, decides whether evidence meets the gate.

- Treat authentication, sandbox, timeout, malformed envelope, and missing-tool
  failures as infrastructure failures, not implementation failures.
- After the same substantive blocker fails twice, change provider or approach.
  After a third failure, stop and surface the evidence instead of spending more
  quota blindly.
- Do not merge, push, deploy, or mutate external systems unless the user has
  authorized that effect.
- Record provider, role, quota state, start revision, output artifact, commands,
  verdict, elapsed time, and usage when available. This receipt is the input to
  later evaluation; it is not proof that the method improved.

Read [methodology and limits](references/methodology.md) when changing this
protocol, and [evidence provenance](references/evidence.md) when evaluating how
strongly its current rules are supported.
