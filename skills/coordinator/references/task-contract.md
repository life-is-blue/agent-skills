# Task contract

Freeze substantial delegated work in a file or immutable prompt artifact. The
contract is a context-transfer boundary, not a transcript dump.

## Size and form

- One atomic contract, one dispatch. Do not fragment one dispatch across several
  prompts or require the user to assemble files before work can start. Split an
  oversized objective into independently verifiable dispatches instead.
- Respect the host's prompt or command size limit as a hard bound when the text
  is the dispatch. A contract that does not fit is evidence that the task is too
  large: split it and issue one piece at a time. When the runner can read the
  repository, write the contract to a path and dispatch the path instead, per
  [durable state between rounds](durable-state.md).
- Point at the file that is the specification — test suite, schema, contract
  file, acceptance script, or design document — and give its path. Summarize the
  intended outcome and scope, but do not let that summary replace or override the
  authoritative specification.
- Separate law from advice. A prohibition is binding and must trace to a measured
  fact or a user decision; a suggestion is context the worker may override with a
  recorded reason. Writing advice as law takes away decisions the worker will
  make better in context.
- Keep transport routing out of the role's work. Record provider choice, adapter,
  and infrastructure reroutes in `goal.json` and the coordinator receipt; do not
  tell an already-dispatched worker to invoke the adapter that launched it.
  Include nested delegation only when it is itself part of the intended outcome.

## Fields

Include only fields that change execution:

1. **Outcome:** the observable result and why it matters.
2. **Workspace:** repository, isolated worktree, branch, and starting revision.
3. **Scope:** editable allowlist and protected paths or interfaces.
4. **Known facts:** measured baselines, authoritative local commands, and
   contract uncertainties. Label assumptions.
5. **Priority order:** which property wins when requirements conflict.
6. **Work:** bounded steps or decisions, with dependencies made explicit.
7. **Acceptance:** exact checks, required evidence, and numeric floors that may
   not regress, per [ground truth and gates](ground-truth.md).
8. **Reverse proof:** for silent-failure risks, run the procedure in
   [ground truth and gates](ground-truth.md) and paste both outputs.
9. **Stop conditions:** retry bound, out-of-scope findings, and blocked protocol.
   A well-documented blocked case is a valid delivery; a worse result presented as
   success is not.
10. **Delivery envelope:** changed files, commands and exit codes, unresolved
    issues, revision, and concise result. For a portable run, declare the JSON
    result path and use the implementation envelope in
    [the runtime contract](runtime-contract.md).
11. **Disclosed calls:** one labeled section listing every decision taken on the
    user's behalf and every unverified assumption. It is the section a reviewing
    human reads first, so a wrong call is vetoed before it is implemented rather
    than after.

For fast mode, outcome, workspace, scope, acceptance, and delivery may be enough.
For a multi-round run, open with a read-back of the standing constraints and keep
a durable ledger, so a resumed worker neither repeats completed work nor proceeds
on a misread goal; see
[durable state between rounds](durable-state.md).

Before dispatching, read the contract side of
[the standing withheld checks](withheld-checks.md). Most rejections come from a
small set of recurring shapes, and wording the contract so a shape cannot arise
costs less than finding it in review and paying for a repair round.

## Exclusions

Do not include credentials, hidden reviewer checks, full unrelated chat history,
or authorization for external effects the user did not grant. A worker may
challenge a false task assumption with evidence; the controller must resolve the
contract instead of forcing implementation to match a disproven premise.

## Narrow fix after a failed review

Do not reissue the whole contract to repair a few findings. Write a short
contract that states what already passed and must not be redone, then each
finding with its expected and actual value, and the acceptance evidence for the
repair alone. Carry the previous numeric floors forward so the fix cannot regress
what the earlier rounds established.

When a finding turns out to be a defect in the contract rather than in the
implementation, say so explicitly, cite the file and line that settles it, and
instruct the worker to leave the correct behavior alone. An unmarked correction
invites the worker to change working code into broken code.
