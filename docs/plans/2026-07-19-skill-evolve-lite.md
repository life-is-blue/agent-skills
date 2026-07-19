# Skill Evolve Lite

## Goal

Add a portable, protocol-only Skill for improving a target `SKILL.md` from
filesystem-staged task trajectories. Preserve the useful SkillOpt-Lite ideas
without claiming that this repository ships benchmark adapters, evaluators, or
model access.

## Decisions

- Name the Skill `skill-evolve-lite` and classify it as `protocol-only`.
- Require the host project to supply immutable train/validation/test splits, a
  rollout command, a machine-readable evaluator result, and per-case traces.
- Keep training traces available for diagnosis, validation examples opaque to
  the optimizer, and test data unused until the final one-shot report.
- Mine cross-trajectory failure consensus and apply one minimal Skill diff per
  round. Reject single-example patches without corroborating evidence.
- Compare candidates with the current accepted revision and retain a separate
  historical best. Roll back rejected candidates and record every decision.
- Treat repeated validation reuse as a finite budget: require a round cap,
  patience limit, meaningful-improvement threshold, and explicit cost ceiling.
- Default to Skill text optimization. Permit harness optimization only as a
  separately declared experiment with an editable allowlist, denylisted data
  and evaluator code, smoke checks, isolated Git state, and human approval for
  the initial structural change.
- Cite SkillOpt-Lite as inspiration, but do not copy or vendor its prompts or
  describe its repository code as bundled here.

## Deliverables

- `skills/skill-evolve-lite/SKILL.md`: concise execution and safety protocol.
- `skills/skill-evolve-lite/references/experiment-contract.md`: host contract,
  artifact layout, result schema, gate semantics, and audit receipt.
- `skills/skill-evolve-lite/references/coding-agent-host.md`: optional execution
  arrangement that keeps candidate generation separate from validation control.
- One `protocol-only` entry in `skills/catalog.json`.

## Acceptance

- Frontmatter contains only `name` and `description` and matches the directory.
- The Skill explicitly checks host prerequisites and stops before any mutation
  when the experiment contract is incomplete.
- The protocol prevents validation/test leakage, evaluator edits, uncontrolled
  scope expansion, and direct mutation of the canonical branch.
- Every round is reproducible from the start revision, candidate diff, rollout
  identifiers, metric result, and gate receipt.
- `python3 scripts/validate_repo.py` and `python3 -m pytest -q` pass.

## Forward-test evidence

On 2026-07-19, a sandboxed Codex session was launched through the repository's
`coding-agent-run` adapter in a detached worktree and asked to improve
`search-docs` with this Skill. It inspected the repository, found no fixed task
splits or task-level evaluator, made no files changes, and stopped at the
pre-mutation boundary. This is the intended negative result.

The first launch also exposed a real adapter regression: Codex CLI 0.144.6
requires the global `--ask-for-approval` option before `exec`. That compatibility
fix is recorded separately in `2026-07-19-codex-cli-compatibility.md`.

## Sources checked

- [SkillOpt-Lite paper](https://arxiv.org/abs/2607.03451)
- [SkillOpt-Lite repository](https://github.com/EvolvingLMMs-Lab/SkillOpt-Lite)
- The public LiveMath and SpreadsheetBench loop prompts were inspected for
  executable behavior and consistency. Their benchmark-specific commands and
  stale split-size literals are intentionally not reproduced.
