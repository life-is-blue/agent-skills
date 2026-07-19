---
name: skill-evolve-lite
description: Improve an existing SKILL.md or a separately scoped agent harness through filesystem-staged task trajectories, cross-case failure consensus, held-out validation gates, rollback, and auditable best-version tracking. Use when a host project has a real task evaluator and fixed train/validation/test splits and the user asks to optimize, evolve, tune, or experimentally improve a Skill or agent harness; do not use for ordinary authoring, structural linting alone, or projects without reproducible task-level evaluation.
---

# Skill Evolve Lite

Run a bounded experiment that proposes one small candidate per round and keeps
only measured improvements. Treat this Skill as an execution protocol: it does
not bundle benchmark adapters, evaluators, model access, or a universal runner.

## Establish the experiment

Read [the experiment contract](references/experiment-contract.md). Require the
host repository to record every required field before launching a rollout.
When a monitored Coding Agent generates candidates, also read
[the Coding Agent host arrangement](references/coding-agent-host.md). Keep the
parent controller responsible for evaluation and gate decisions.

Stop before mutation when any of these conditions holds:

- train, validation, and test identities are not fixed and disjoint;
- the evaluator cannot emit a machine-readable task metric;
- validation cases or expected answers would be visible to the optimizer;
- the editable paths, metric direction, gate threshold, budget, or rollback
  method are unspecified;
- the only available check is syntax, formatting, or repository validation;
- the work would modify the canonical checkout instead of an isolated Git
  branch or worktree.

Hash or otherwise identify the data splits, evaluator, initial target, and
start revision. Run the repository's static checks, then measure the untouched
target on the full validation split. Save it as both `current` and `best`.
Never use test results to select a candidate.

## Run one Skill round

Perform these steps once per round:

1. Roll out the currently accepted Skill on a seeded train batch. Write one
   trace file per case and keep success traces as controls.
2. Explore traces through filesystem search and selective reading. Do not load
   the entire trajectory corpus into one prompt when targeted inspection works.
3. Cluster failures by root cause. Require corroboration from at least two
   independent cases before treating a pattern as consensus; label isolated
   failures instead of patching for them.
4. Choose one high-impact, Skill-addressable cause. Reject causes belonging to
   the model, evaluator, missing tools, data, or harness unless the declared
   experiment explicitly makes that surface editable.
5. Apply the smallest coherent diff to the target `SKILL.md`. Preserve its
   contract, valid frontmatter, and unrelated behavior. Make no second patch in
   the same round.
6. Run static checks. Reject and restore the pre-round snapshot on failure.
7. Evaluate the candidate on the full validation split without exposing case
   contents or answers to the optimizer. Parse the declared result field.
8. Apply the declared gate against `current`: accept only a meaningful
   improvement, treat a result inside the deadband as flat, and otherwise
   reject. Roll back both flat and rejected candidates. Update `best` only when
   the accepted candidate beats the historical best.
9. Write a gate receipt containing the evidence clusters, diff hash, commands,
   split identity, score, decision, and resulting revision.

Restore `best` as `current` after every decision. Use a new deterministic train
seed so the next traces match that on-disk revision. Do not generate the next
batch from a flat or rejected candidate.

## Control validation adaptation

Treat validation reuse as a limited resource, not proof of unlimited
generalization. Set a maximum round count, patience limit, minimum meaningful
improvement, and cost ceiling before round one. Stop when any limit is reached.

Prefer fewer, evidence-backed rounds when the validation set is small. Do not
weaken a gate after seeing an unfavorable result, change the split mid-run, or
select among multiple same-round candidates using repeated validation probes.
If the protocol itself changes, start a new experiment with a new identifier
and baseline.

## Optimize a harness only when declared

Keep Skill evolution as the default surface. For harness evolution:

1. Start a separate experiment; do not edit Skill text and harness code in the
   same round.
2. Declare an exact editable allowlist. Deny changes to the evaluator, data
   loader, split configuration, expected answers, and metric implementation.
3. Diagnose the full initial train failure distribution and present the first
   structural proposal for human approval before patching.
4. Run compilation and a small smoke batch before every full validation gate.
5. Use isolated subprocesses and Git rollback. Reject any out-of-allowlist diff
   automatically.

Do not describe a harness change as general improvement when it only repairs a
benchmark-specific adapter defect. Report that distinction explicitly.

## Finish

Restore the historical best revision. Run the full test split exactly once if
the contract authorized its cost and external effects. Report:

- baseline, best validation, and final test metrics;
- accepted, flat, and rejected rounds;
- the best revision and complete diff;
- failure clusters addressed and remaining;
- model, evaluator, dataset, command, token/time/cost, and seed provenance;
- limitations, including validation reuse and benchmark specificity.

If no candidate clears the gate, retain the baseline and report a valid null
result. Never manufacture progress by keeping a regression.
