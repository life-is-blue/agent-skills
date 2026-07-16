# Repository governance rollout

## Goal

Make the repository's promises match its contents and establish a blocking,
dependency-light quality gate for every Skill contribution.

## Decisions

- Treat `SKILL.md` as the portable protocol. Keep its YAML frontmatter limited
  to `name` and `description`.
- Classify every Skill in a root catalog as `bundled`, `adapter`, or
  `protocol-only`.
- Use MIT as the repository default license. A Skill may carry an additional
  license file when required.
- Support clients through copy-based, protocol-level guidance. Client-specific
  discovery behavior is informative rather than a compatibility promise.
- Run governance checks and existing tests as blocking GitHub Actions checks.
- Fix the `office-mpp` test working-directory dependency now; record its
  placeholder tests as test debt rather than expanding this governance change
  into a domain-test rewrite.

## Changes

1. Add a contribution policy covering required files, distribution classes,
   progressive disclosure, dependency documentation, and acceptance criteria.
2. Add a machine-readable Skill catalog and a standard validation command.
3. Validate catalog/directory parity, portable frontmatter, naming, local
   Markdown targets, referenced bundled paths, shell syntax, Python syntax, and
   the existing test suite.
4. Add a blocking GitHub Actions workflow using the same local command.
5. Rewrite repository-level documentation around the portable protocol and
   accurately label the five current Skills.
6. Make protocol-only Skills explicitly check for host-provided commands before
   following their execution protocols.

## Acceptance

- `python3 scripts/validate_repo.py` succeeds from the repository root.
- `python3 -m pytest -q` succeeds from the repository root.
- Every `skills/*/SKILL.md` has only `name` and `description` in frontmatter and
  has exactly one matching catalog entry.
- All local Markdown links and explicitly referenced repository paths exist.
- README and architecture documentation no longer claim that every Skill ships
  executable code or that the repository contains no runtime code.

## Deferred debt

- Replace the placeholder-heavy `office-mpp` tests with behavior-driven tests
  in a dedicated follow-up.
- Forward-test individual Skills on realistic user prompts separately from the
  governance rollout.
