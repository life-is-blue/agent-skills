# Review contract

Review is a separate evidence-producing role. It is not a request to improve the
implementer's prose or silently fix the work.

## Prepare

- Give the reviewer the intended behavior, starting revision, candidate diff,
  and acceptance commands.
- Prefer a read-only reviewer or an isolated review worktree. Do not let review
  edits contaminate the candidate being judged.
- Expect the brief to be shorter than the task contract and the review run to be
  longer than reading a diff. The brief carries expected values and reproduction
  steps rather than a restated specification, and the reviewer spends its
  capacity rerunning and reproducing.

## Withheld checks

A worker can optimize for checks it sees. When a task has a plausible silent
failure and the controller can derive the expected result from an authority,
withhold that check from the implementer. The source corpus supports withheld
checks as a useful defect-finding mechanism, not a requirement to invent one for
every independent review.

- The controller writes them and keeps them out of the task contract, the
  implementer's prompt, and the role-visible repository state.
- Each check states the input, the expected value, and where that expectation
  came from. Derive expectations from a judge or another authority before the
  review starts; a withheld check with a guessed answer produces argument
  instead of evidence.
- Select the shapes this task can exhibit from
  [the standing withheld checks](withheld-checks.md) rather than composing them
  from scratch. Authoring is the expensive part of review; the shapes recur, the
  expected values do not.
- Re-verify the protections earlier rounds added. A gate is only worth its cost
  while it is still present.
- In a multi-round run, confirm the worker's read-back against the standing
  constraint set, per
  [durable state between rounds](durable-state.md). A fire-and-forget dispatch
  offers no earlier point at which a misread goal can be caught.
- A withheld check can itself be wrong. When the implementer disputes one with
  file, line, or command evidence, the controller resolves the specification
  rather than forcing the implementation to match a disproven expectation.

## Check

1. Inspect the diff and protected paths.
2. Rerun the relevant tests or reproduce the behavior independently.
3. Confirm the judge and gates are intact, per
   [ground truth and gates](ground-truth.md).
4. Run the applicable withheld checks against the candidate.
5. Exercise silent-failure paths: empty output, partial writes, stale state,
   timeouts, misleading exit zero, or disabled assertions as applicable.
6. Check whether implementation and tests merely agree on the same mistaken
   interpretation of the specification.
7. Report findings with severity, file or interface location, evidence, and the
   smallest condition that would clear the blocker.

## Verdict envelope

Write the verdict to the review path declared by the runtime contract, using a
machine-readable equivalent of:

```json
{
  "schema_version": 1,
  "role": "reviewer",
  "verdict": "go",
  "round_id": "round-1",
  "start_revision": "...",
  "candidate_revision": "...",
  "checks": [
    {"id": "focused-tests", "kind": "open", "passed": true,
     "evidence": "command and result"},
    {"id": "dropped-value-is-reported", "kind": "withheld", "passed": false,
     "expected": "...", "actual": "...", "evidence": "command and result"}
  ],
  "blockers": [],
  "spec_uncertainties": [],
  "infrastructure_errors": []
}
```

Report `kind` on every check. Open checks were visible to the implementer;
withheld checks were not. Keeping the two countable is what later shows whether
withheld checks are earning their cost, and a run where they never fail is a
signal that they were aimed at what the contract already required.

`go` requires non-empty evidence for every required check. A malformed result,
missing command evidence, unavailable dependency, or sandbox failure is not a
`no-go` implementation verdict; classify it as infrastructure failure and stop
or reroute.

The controller independently confirms the repository gate before integration.
A reviewer verdict never grants permission to merge, push, deploy, or mutate an
external system.
