# AGENTS.md

## Precedence

Subject to higher-priority host instructions, precedence is:
explicit user instruction > this file > a skill's SKILL.md > its references.
Use this hierarchy for real conflicts. Specificity only refines compatible
rules or resolves rules at the same level; it cannot override a higher-level
rule. Resolve such conflicts directly and disclose material interpretations
in the handoff.

## Workflow

1. Read the relevant `skills/<name>/SKILL.md` and only the references routed for
   the current operation.
2. Inspect the worktree and preserve unrelated user changes.
3. Complete the requested outcome with the smallest coherent change.
4. Update existing durable documentation only when current behavior or a public
   contract changed.
5. Run `python3 scripts/validate_repo.py` and risk-proportionate relevant tests.

Do not create task plans, audit reports, changelogs, or duplicate READMEs unless
the user requests them or they are required runtime or legal artifacts.
Keep execution state separate from durable project documentation. Discussion
alone does not require repository files; update terminology or decision docs
when the current contract changes. Git history records completed change history;
repository documents describe current behavior.

## Execution authority

- Treat the user's request as authorization for the ordinary, in-scope local
  reads, edits, and verification needed to complete it. Do not ask for approval
  already conveyed by that request.
- Resolve repository paths, current revision, tool availability, and other
  observable facts by inspection. Anything a measurement can settle is not a
  question. Make reversible implementation choices when they do not materially
  change scope, and state important assumptions in the handoff.
- Ask exactly one consolidated clarification when a missing choice would
  materially change the outcome AND inspection cannot settle it. Skills may
  specialize the question format per tier (frontier interview for vague
  direction, optioned questions before dispatch); this rule is the fallback
  when no tier applies.
- Gated effects require explicit scope: commit, push, PR creation, publishing,
  deployment, deletion, writes outside the requested workspace, credentials,
  provider spending, permission bypass. One request naming several gated
  effects satisfies all of them — list every effect once, together, immediately
  before executing; do not confirm each separately. Authorization for one does
  not extend to effects not named.
- A request to create, fix, update, or optimize includes implementation and
  verification. A request to review, explain, or diagnose is read-only unless
  it also asks for fixes.
- Approval checks belong immediately before the gated effect. Once granted,
  continue through verification without asking again unless the target, scope,
  risk, or cost materially changes.
- Decide important reversible judgment calls within the authorized scope with a
  safe default and disclose them in one labeled place. Disclosure is not an
  approval request or a substitute for approval; silence is not authorization.
  When a material answer or approval is missing, pause only dependent steps and
  continue independent authorized work.
- Do not infer a deletion or credential-management exception from ordinary edit
  authority. Removing code within an authorized edit does not itself authorize
  deleting files, data, or resources. Distinguish using already-configured
  authentication for an authorized operation from creating, changing, exporting,
  or disclosing credentials; the latter require explicit scope. Place runtime
  state in an allowed location using existing configuration options; otherwise
  obtain authorization for the required outside-workspace write.

## Completion and recovery

- Continue until the requested outcome is implemented and verified, or until a
  concrete blocker requires user action. A failed command or delegated worker
  is evidence to diagnose, not an automatic stop condition.
- Retries live at three layers; never apply one layer's count to another:
  single command (retry only with an understood cause and a changed relevant
  input), a task brief's inner loop (the brief's own stop rules, e.g. three
  consecutive acceptance failures moves to the next item), and the run-level
  repair bound (declared before dispatch, mechanically enforced by the
  coordinator runner).
- Use a safe fallback within the same scope when available; do not
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
- Skill directories are distributed by copying or symlinking the directory
  alone; repo-root files (this file included) do not travel with them.
  Therefore a Skill must be self-contained: restate every behavioral rule it
  relies on inside its own directory, in its own words. Cross-skill repetition
  of a rule is the price of portability, not debt. Depending on a sibling
  Skill is allowed only with an explicit install instruction in SKILL.md.
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
