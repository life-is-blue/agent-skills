# AGENTS.md

## Workflow

1. Read the relevant `skills/<name>/SKILL.md` and its routed references.
2. Inspect the worktree and preserve unrelated user changes.
3. Make the smallest complete change and update durable documentation.
4. Run `python3 scripts/validate_repo.py` and relevant tests.

Do not create task plans, audit reports, changelogs, or duplicate READMEs unless
they are required runtime or legal artifacts. Git history records completed
change history; repository documents describe current behavior.

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
