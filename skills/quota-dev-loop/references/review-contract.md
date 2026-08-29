# Review contract

Review is a separate evidence-producing role. It is not a request to improve the
implementer's prose or silently fix the work.

## Prepare

- Give the reviewer the intended behavior, starting revision, candidate diff,
  and acceptance commands.
- Keep at least one important adversarial check out of the implementation prompt
  when the task risk justifies an independent check.
- Prefer a read-only reviewer or an isolated review worktree. Do not let review
  edits contaminate the candidate being judged.

## Check

1. Inspect the diff and protected paths.
2. Rerun the relevant tests or reproduce the behavior independently.
3. Exercise silent-failure paths: empty output, partial writes, stale state,
   timeouts, misleading exit zero, or disabled assertions as applicable.
4. Check whether implementation and tests merely agree on the same mistaken
   interpretation of the specification.
5. Report findings with severity, file or interface location, evidence, and the
   smallest condition that would clear the blocker.

## Verdict envelope

Use a machine-readable equivalent of:

```json
{
  "verdict": "go",
  "start_revision": "...",
  "candidate_revision": "...",
  "checks": [
    {"id": "focused-tests", "passed": true, "evidence": "command and result"}
  ],
  "blockers": [],
  "spec_uncertainties": [],
  "infrastructure_errors": []
}
```

`go` requires non-empty evidence for every required check. A malformed result,
missing command evidence, unavailable dependency, or sandbox failure is not a
`no-go` implementation verdict; classify it as infrastructure failure and stop
or reroute.

The controller independently confirms the repository gate before integration.
A reviewer verdict never grants permission to merge, push, deploy, or mutate an
external system.
