# Ground truth and gates

Machine-checkable truth has to come from outside the implementer. Without an
external authority, the implementation and its tests can agree on the same
mistaken reading of the specification and still report success.

## Differential judge

When a reference implementation, legacy engine, published contract, or
authoritative dataset exists, make it the judge instead of describing expected
behavior in prose:

- Write the smallest judge that emits the reference answer for a given input,
  and compare parsed structures rather than formatted text.
- Obtain expected values by running the judge, not by reasoning about what it
  should return.
- Cover the boundaries the reference actually has, including defects that callers
  already depend on. Mark each preserved oddity in place so a later reader does
  not silently correct it.
- Keep the judge outside the code under test, and keep enough cases that a
  single fixture cannot carry the whole comparison.

## Judge immutability

- Freeze the judge for the run. The implementer may not edit, replace, or route
  around it, and may not relax the comparison, delete cases, or compare fewer
  fields than before.
- The reviewer confirms the judge is unmodified and that tampering with it turns
  the gate red.
- When outputs cannot be aligned, the correct delivery is a report: the
  disagreeing fields with both raw outputs. A documented blocked case is an
  acceptable result; a green gate obtained by weakening the judge is not.

## Baseline ratchet

State gates as numbers that cannot silently regress:

- a floor on the count of passing checks, measured before the work starts;
- zero skipped, ignored, or disabled cases;
- named prohibitions on the cheapest routes to green, because a worker optimizes
  the gate it was given: skip markers, trivially true assertions, deleted cases,
  mocking the subject under test, or a command suffixed to always succeed.

A count that may only move up is cheap to verify and removes the most common
silent failure, which is a gate that passes because it stopped checking.

## Reverse proof

For any protection whose failure would be silent, prove the gate works rather
than asserting it:

1. Break the protection once, deliberately.
2. Show the gate turning red, with the actual output.
3. Restore it and show it green again.
4. Confirm the working tree is clean afterwards.

Ask "if this broke, who would find out". When the answer is "nobody", a reverse
proof is required. A monitor that cannot be shown to fire is indistinguishable
from one that is disconnected.
