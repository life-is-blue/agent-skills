# Task contract

Freeze substantial delegated work in a file or immutable prompt artifact. The
contract is a context-transfer boundary, not a transcript dump.

## Size and form

- One contract, one dispatch. Do not split a single task across several prompts
  or require the user to assemble files before work can start.
- Respect the host's prompt or command size limit as a hard bound. A contract
  that does not fit is evidence that the task is too large: split it and issue
  one piece at a time.
- Point at the file that is the specification — test suite, schema, contract
  file, acceptance script, or design document — and give its path. Do not
  paraphrase it. A paraphrase becomes a second specification that will diverge
  from the first, and the worker cannot tell which one governs.
- Separate law from advice. A prohibition is binding and must trace to a measured
  fact or a user decision; a suggestion is context the worker may override with a
  recorded reason. Writing advice as law takes away decisions the worker will
  make better in context.

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
    issues, revision, and concise result.

For fast mode, outcome, workspace, scope, acceptance, and delivery may be enough.
For deep mode, add a short progress artifact so a resumed worker does not repeat
completed work.

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
