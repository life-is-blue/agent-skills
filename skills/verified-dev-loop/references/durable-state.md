# Durable state between rounds

A contract is bounded by the runner's prompt limit, while the invariants a
multi-round run must preserve keep accumulating. Restating them consumes more of
that bound every round, and the choice of what to restate lives only in the
coordinator's context, where nothing checks it. Put the state that must outlive a
single dispatch in the repository and let the contract point at it.

Use the public run directory and private host-state split in
[the runtime contract](runtime-contract.md) when more than one coordinator or
transport must discover the same run.

## Constraint set

Keep one file for what must hold in every round: prohibitions, purity or layering
rules, preserved defects that callers already depend on, and forbidden strings.

- Record for each entry whether a mechanical guard enforces it, and name the
  guard. An unguarded entry is a promise; a guarded one is a fact.
- When review finds a recurring, mechanically detectable violation, prefer a
  guard to stronger wording. Converting it into a lint rule, meta-test, or gate
  is what stops it from consuming contract space and reviewer attention in every
  later round. Do not add a guard merely because an arbitrary count was reached;
  first confirm that it enforces the intended rule without false positives.
- Cite this file by path from the contract and restate nothing out of it. A
  restatement becomes a second specification that can diverge from the first.

## Plan ledger

Keep the plan durable, not just the current task: the ordered dispatches this
objective needs, which are finished, which remain, and the numeric floors reached
so far.

- Record status per planned dispatch and how many are still outstanding, so
  remaining scope does not exist only in the coordinator's context. In the source
  corpus it did, and the user had to ask for a re-estimate of the remaining
  contracts twice in one run.
- Record the current floors, so the next contract carries them forward without
  recounting them by hand.
- Keep it as current state. It is a ledger, not a changelog or a narrative of
  what happened.

## Contract files

When the runner can read the repository, write the contract to a path and
dispatch the path rather than the text.

- The prompt bound stops applying, so a contract is split because the work is
  too large, not because the text is too long.
- Contracts become diffable between rounds, and the reviewer can cite the
  original wording instead of a relayed paraphrase.
- When the runner cannot read files, the bound is real. An oversized contract
  then means the task is too large and should be split.

## Read-back before work

Make the first task a read-back, not only a baseline check: the worker reads the
constraint set and the ledger, then writes back in a few lines the goal as it
understands it, the invariants it will not violate, and the largest risk it sees.

A baseline check confirms numbers, but drift happens in the reading. At least one
round in the source corpus was rejected over a defect in the contract rather than
in the implementation, and it surfaced only after the work was complete and
reviewed.

A read-back is only a gate if something acts on a mismatch. When the dispatch is
interactive, the controller checks it before the worker proceeds. When the
dispatch is fire-and-forget, the contract must make a mismatch a stop condition
the worker applies to itself, and the reviewer must confirm the read-back matches
the constraint set. The corpus required this receipt and nobody checked it, which
makes it a record rather than a gate.
