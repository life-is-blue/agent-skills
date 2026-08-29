# Methodology and limits

## Stable principles

- Keep host facts out of the method. Which CLI is installed, cheap, or authorized
  changes independently of how the work should be run, so it belongs in a
  one-time host setup rather than in the protocol.
- Keep provider adapters thin and provider-specific, because CLI envelopes,
  permissions, exit codes, and resume behavior differ materially.
- Transfer frozen task contracts, not entire coordinator conversations.
- Keep cross-round invariants, the remaining plan, and the contracts themselves in
  the repository rather than in each prompt. A prompt bound is fixed while
  invariants accumulate, and a constraint that recurs deserves a mechanical guard
  rather than stronger wording.
- Separate planning, implementation, and acceptance when the risk justifies the
  coordination cost.
- Treat implementation summaries as claims. Tests, diffs, files, and reproduced
  behavior are evidence.
- Establish ground truth outside the implementer, and state gates as numbers that
  may only move up. An implementation and its own tests can agree on the same
  mistaken reading of the specification.
- Withhold the checks that would expose a plausible-but-wrong result. A worker
  optimizes what it can see, so visible gates mostly confirm what the contract
  already demanded.
- Route by relative cost and capability, which are observable, rather than by
  remaining balance, which is not. Reserve the expensive context for decisions
  and give high-frequency iteration to the cheapest provider that can carry it.
- Prefer orthogonal work. Independent implementation, review, negative testing,
  and contract investigation are worth more than asking several models for
  interchangeable summaries, and capacity left unused is cheaper than a round
  spent on work nobody needed.
- A failed premise should change the task contract. It should not force a worker
  to implement a known-wrong specification.

## What is not established

- No provider is permanently best for a role. Revalidate CLI behavior after
  upgrades and update host profiles.
- More provider calls have not been proven to improve throughput. Record cycle
  time, accepted output, defect findings, and quota usage before claiming an
  improvement.
- Independent models can share the same specification error. Engine diversity
  does not replace contract validation or real-environment tests.
- Balance-based scheduling is design, not a finding, which is why it is absent
  here. The source corpus optimized for context preservation and cost arbitrage
  and contains no subscription-quota evidence; cost arbitrage between an
  expensive coordinator and a cheaper implementer is the part it supports.
- The recurring failure shapes come from one corpus. Treat the standing withheld
  checks as a starting library to extend from new traces, not a closed set.
- This protocol does not expose subscription balances, install CLIs, authenticate
  accounts, create worktrees, or execute providers by itself.

## Evolving the protocol

Change a rule only when multiple traces show the same addressable failure or a
controlled comparison clears a predefined gate. Keep task identity, evaluator,
baseline, and validation cases fixed when claiming measured improvement. A
single successful project is evidence for a candidate rule, not proof of a
universal workflow.
