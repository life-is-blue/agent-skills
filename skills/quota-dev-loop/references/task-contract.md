# Task contract

Freeze substantial delegated work in a file or immutable prompt artifact. The
contract is a context-transfer boundary, not a transcript dump.

Include only fields that change execution:

1. **Outcome:** the observable result and why it matters.
2. **Workspace:** repository, isolated worktree, branch, and starting revision.
3. **Scope:** editable allowlist and protected paths or interfaces.
4. **Known facts:** measured baselines, authoritative local commands, and
   contract uncertainties. Label assumptions.
5. **Priority order:** which property wins when requirements conflict.
6. **Work:** bounded steps or decisions, with dependencies made explicit.
7. **Acceptance:** exact checks and required evidence; prohibit weakening or
   deleting the gate to make it pass.
8. **Reverse proof:** for silent-failure risks, deliberately make the protection
   fail once and show that the gate detects it.
9. **Stop conditions:** retry bound, out-of-scope findings, and blocked protocol.
10. **Delivery envelope:** changed files, commands and exit codes, unresolved
    issues, revision, and concise result.

For fast mode, outcome, workspace, scope, acceptance, and delivery may be enough.
For deep mode, add a short progress artifact so a resumed worker does not repeat
completed work.

Do not include credentials, hidden reviewer checks, full unrelated chat history,
or authorization for external effects the user did not grant. A worker may
challenge a false task assumption with evidence; the controller must resolve the
contract instead of forcing implementation to match a disproven premise.
