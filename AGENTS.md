# AGENTS.md

## Workflow

1. Read the relevant `skills/<name>/SKILL.md` and only the references routed for
   the current operation.
2. Inspect the worktree and preserve unrelated user changes.
3. Complete the requested outcome with the smallest coherent change.
4. Update existing durable documentation only when current behavior or a public
   contract changed.
5. Run `python3 scripts/validate_repo.py` and risk-proportionate relevant tests.

Do not create task plans, audit reports, changelogs, or duplicate READMEs unless
they are required runtime or legal artifacts. Git history records completed
change history; repository documents describe current behavior.

## Execution authority

- Treat the user's request as authorization for the ordinary, in-scope local
  reads, edits, and verification needed to complete it. Do not ask for approval
  already conveyed by that request.
- Resolve repository paths, current revision, tool availability, and other
  observable facts by inspection. Make reversible implementation choices when
  they do not materially change scope, and state important assumptions in the
  handoff.
- Ask one consolidated clarification only when a missing choice would
  materially change the outcome, create an irreversible or external effect, or
  require credentials, spending, permission bypass, or scope expansion. Do not
  turn a recommendation or a request for confirmation into a prerequisite when
  a safe default exists.
- A request to create, fix, update, or optimize includes implementation and
  verification. A request to review, explain, or diagnose is read-only unless
  it also asks for fixes. Commit, push, PR creation, publishing, deployment,
  deletion, and writes outside the requested workspace require explicit scope;
  authorization for one does not imply the others.
- Approval checks belong immediately before the gated effect. Once granted,
  continue through verification without asking again unless the target, scope,
  risk, or cost materially changes.

## Completion and recovery

- Continue until the requested outcome is implemented and verified, or until a
  concrete blocker requires user action. A failed command or delegated worker
  is evidence to diagnose, not an automatic stop condition.
- Retry only when the cause is understood and the retry changes something
  relevant. Use a safe fallback within the same scope when available; do not
  silently broaden permissions, switch an explicitly chosen provider, or
  replace a requested workflow with a materially different one.
- Do not claim completion from a worker report or zero exit code alone. Review
  the resulting diff or artifact and the meaningful verification output.
- If blocked, report the achieved work, exact blocker, evidence, and smallest
  user action needed. Do not stop merely because an optional tool, ideal test,
  or nonessential input is unavailable.

## Skill contract

- Use `skills/<name>/SKILL.md` as the Skill entrypoint.
- Keep frontmatter to `name` and `description`; make the directory and name
  identical lowercase hyphen-case.
- Put triggering conditions in `description`, core procedure in `SKILL.md`, and
  optional detail in directly linked `references/` files.
- Create only resources the Skill uses. State dependencies, commands, inputs,
  outputs, side effects, and failure handling without claiming host-provided
  code is bundled.
- Update `skills/catalog.json` when adding, deleting, or renaming a Skill.
- Classify delivery as `bundled`, `adapter`, or `protocol-only` according to the
  implementation actually present in the Skill directory.
- Pin upstream snapshots to a commit and retain their hash, provenance, and
  license. Do not edit a snapshot in place.

## Verification

- Treat local `<command> --help` plus a minimal smoke as the authority for an
  external CLI. Do not rely on a documentation description when behavior
  differs.
- Keep network, paid API, secret-dependent, and external-state-changing calls
  out of CI.
- Review diffs and structured results; a zero exit code alone is insufficient.
- Do not describe the current pytest suite as complete domain coverage:
  `office-mpp` still contains placeholder tests.
