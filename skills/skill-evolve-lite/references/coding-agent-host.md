# Coding Agent host arrangement

Use a monitored Coding Agent as the candidate generator, not as the evaluator
or experiment controller. This separation keeps held-out material outside the
optimizer's context and makes retries and rollback deterministic.

## Ownership

Assign responsibilities as follows:

| Component | Owns |
|---|---|
| Parent controller | Contract checks, split access, baseline, validation, gate, rollback, best tracking, budget and receipts |
| Target runtime | Train task execution and per-case trajectory capture |
| Coding Agent | Train-trace exploration, consensus diagnosis and one candidate diff |
| Evaluator | Structured metric calculation only; no candidate editing |

Never give the Coding Agent validation/test case bodies, expected answers,
evaluator source that reveals answers, credentials, or authority to change the
contract. Give it only the accepted target, train traces, editable/protected
paths, round identifier, and static-check command.

## Session topology

Use one isolated Git worktree for the experiment and one fresh Coding Agent
session per round. Pin one provider and model for the entire experiment; do not
use automatic provider fallback between rounds because it changes the
optimizer. Record the runner session ID in the round receipt.

The parent should execute this sequence:

```text
preflight → baseline validation
for each round:
  parent: produce seeded train traces from current best
  coding agent: inspect train traces and make one candidate diff
  parent: enforce diff allowlist and run static checks
  parent: run opaque full validation and parse structured result
  parent: accept as best or roll back, then write gate receipt
parent: restore best and run test once
```

Launch with the repository's `coding-agent-run` adapter when it is installed,
or an equivalent monitored runner supplied by the host. Include the worktree,
start revision, target, artifact paths, one-patch limit, protected paths, static
checks, and external-write authorization in the prompt. Do not include the
validation command if running it would expose held-out inputs to the optimizer.

## Failure handling

- Treat provider launch failure as an execution failure, not a rejected Skill
  candidate. Preserve the round number and retry only after diagnosing it.
- Do not silently change provider or model. Start a new experiment if a change
  is necessary.
- Reject out-of-allowlist edits before evaluation.
- Treat a successful process exit as insufficient; inspect the diff and verify
  the declared static checks from the parent.
- Stop on missing or malformed artifacts rather than reconstructing scores from
  chat prose.

For a negative preflight test, point the Coding Agent at a target without a
task evaluator. It should inspect safely, leave the target unchanged, and name
the missing contract fields. This verifies guardrails but does not demonstrate
that the optimization loop improves task performance.
