# Methodology and limits

## Stable principles

- Put frequently changing routing knowledge in readable profiles and references;
  keep provider adapters thin and provider-specific because CLI envelopes,
  permissions, exit codes, and resume behavior differ materially.
- Transfer frozen task contracts, not entire coordinator conversations.
- Separate planning, implementation, and acceptance when the risk justifies the
  coordination cost.
- Treat implementation summaries as claims. Tests, diffs, files, and reproduced
  behavior are evidence.
- Spend urgent quota on orthogonal work. Independent implementation, review,
  negative testing, and contract investigation are more valuable than asking
  several models for interchangeable summaries.
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
- This protocol does not expose subscription balances, install CLIs, authenticate
  accounts, create worktrees, or execute providers by itself.

## Evolving the protocol

Change a rule only when multiple traces show the same addressable failure or a
controlled comparison clears a predefined gate. Keep task identity, evaluator,
baseline, and validation cases fixed when claiming measured improvement. A
single successful project is evidence for a candidate rule, not proof of a
universal workflow.
