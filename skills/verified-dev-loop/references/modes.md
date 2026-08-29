# Operating modes

Choose by risk and coordination value, not by task size alone. A tiny permission
change may need deeper review than a large generated fixture update.

## Fast

Use for a localized, reversible change with an obvious test surface.

- One provider implements.
- The controller reviews the diff and reruns the focused check, keeping at least
  one expectation to itself instead of announcing every check in advance.
- Add a second provider only when it can produce a useful targeted check without
  delaying the main path.
- A compact task contract is enough; omit sections that do not change behavior.

## Standard

Use for an ordinary feature, bug fix, or bounded refactor with multiple files or
non-trivial behavior.

- A coordinator freezes scope and acceptance evidence.
- One provider implements in an isolated branch or worktree.
- A different provider reviews the diff and runs the controller's withheld
  checks.
- The controller reruns the repository gate before integration.
- A failed review produces a narrow fix contract, not a reissued task.

This is the default, because it creates two useful, non-duplicative units of
work: implementation and independent verification.

## Deep

Use for migrations, foundational refactors, security-sensitive changes,
irreversible data work, or tasks with an uncertain contract.

- First use one provider to investigate the contract and failure modes.
- Establish an external judge and numeric floors before implementation starts,
  per [ground truth and gates](ground-truth.md).
- Freeze a sequence of bounded task contracts rather than one unbounded prompt.
- Use an implementer and an engine-diverse reviewer.
- Scale withheld checks with risk, and re-verify the protections earlier rounds
  added rather than only the current round's work.
- Add adversarial design, negative tests, or a competing approach only when the
  result can change the decision.
- Keep explicit human gates for scope changes and irreversible effects.

## Upgrade or downgrade

Upgrade when the contract is uncertain, failures are expensive, the change is
hard to reverse, or the first review finds a systemic issue. Downgrade when the
change becomes localized and the remaining checks are mechanical. Do not keep a
deep loop running merely because it has already consumed substantial capacity.
