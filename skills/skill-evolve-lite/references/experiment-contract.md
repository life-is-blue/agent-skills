# Experiment contract

Record this contract in the host repository before optimization. Use repository
paths and commands that another operator can rerun; never embed secrets.

## Required declaration

```yaml
experiment_id: unique-id
mode: skill                 # skill or harness
start_revision: git-sha
target: path/to/SKILL.md
editable_paths: [path/to/SKILL.md]
protected_paths: [evaluator, data, split-config, expected-answers]
splits:
  train: {id: immutable-id, count: 0}
  validation: {id: immutable-id, count: 0}
  test: {id: immutable-id, count: 0}
commands:
  static_check: argv-or-documented-command
  train_rollout: argv-or-documented-command
  validation: argv-or-documented-command
  test: argv-or-documented-command
metric:
  field: hard_score
  direction: maximize        # maximize or minimize
  min_delta: 0.01
  deadband: 0.005
limits:
  rounds: 5
  batch_size: 20
  patience: 3
  max_wall_time: documented
  max_cost: documented
artifacts: .skill-evolve/unique-id
rollback: isolated-git-worktree
```

Use argument arrays or checked-in wrapper commands when shell quoting would be
ambiguous. State whether commands call paid APIs, use network access, or modify
external systems. Require separate authorization for effects outside the
declared experiment.

## Evaluator result

Make every evaluation write one JSON result atomically:

```json
{
  "schema_version": 1,
  "run_id": "round-2-validation",
  "split_id": "validation-v1-sha256:...",
  "target_sha256": "...",
  "evaluator_revision": "git-sha-or-content-hash",
  "seed": 2,
  "case_count": 35,
  "hard_score": 0.61,
  "soft_score": 0.74,
  "traces": null
}
```

Require train rollouts to point `traces` to a directory containing one stable,
uniquely named file per case. Permit validation and test results to omit traces
so the optimizer cannot inspect held-out examples.

Reject results whose split, target hash, evaluator revision, seed, or case
count differs from the command being gated. Do not scrape a score from prose
when a structured result can be produced.

## Artifact layout

```text
.skill-evolve/<experiment-id>/
├── contract.yaml
├── baseline/result.json
├── rounds/<n>/
│   ├── before.md
│   ├── train-result.json
│   ├── traces/{failed,passed}/<case-id>.md
│   ├── diagnosis.md
│   ├── candidate.md
│   ├── candidate.diff
│   ├── validation-result.json
│   └── gate.json
├── best.md
└── final/test-result.json
```

Keep raw traces out of Git when they contain private data, but retain their
content hashes and approved storage location in the receipt. Never put
credentials, hidden answers, or validation/test case bodies in an agent prompt.

## Gate receipt

Record at least:

```json
{
  "round": 2,
  "before_sha256": "...",
  "candidate_sha256": "...",
  "diff_sha256": "...",
  "train_run_id": "round-2-train",
  "consensus_clusters": ["missing-retry-boundary"],
  "validation_run_id": "round-2-validation",
  "current_score": 0.58,
  "candidate_score": 0.61,
  "decision": "accept_new_best",
  "resulting_sha256": "..."
}
```

Normalize improvement as candidate minus current for maximization and current
minus candidate for minimization. Accept and mark a new best when normalized
improvement is at least `min_delta`. Mark a result flat when its absolute
improvement is at most `deadband`; otherwise reject it. Restore the prior best
for both flat and reject decisions. Require `0 <= deadband < min_delta`.

A deadband handles known evaluator noise; it is not permission to retain an
unmeasured candidate. If metric noise is large enough to require statistical
testing or repeated trials, declare that procedure and its seed budget before
the baseline instead of improvising after seeing candidate scores.

## Provenance

This protocol is inspired by the filesystem trajectory exploration, consensus
mining, and independent validation gating described in
[SkillOpt-Lite](https://arxiv.org/abs/2607.03451) and its
[public research implementation](https://github.com/EvolvingLMMs-Lab/SkillOpt-Lite).
It does not vendor that implementation or claim compatibility with its
benchmark-specific `run.sh` interfaces.
