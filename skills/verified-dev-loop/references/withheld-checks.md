# Standing withheld checks

In the source corpus, 20 rejected verdicts among 32 distinct relayed verdict
texts fell into the six shapes below. None of them required insight specific to
that project: the
failures were shaped by delegation itself, not by the domain. So do not invent
withheld checks from scratch each round. Select the shapes this task can exhibit,
fill in the input and the authoritative expected value, and spend the saved
effort on getting the expectations right.

Each shape below gives what to withhold from the implementer, and the contract
wording that prevents the shape from arising in the first place. Use both
directions: the review side finds the failure, the contract side is cheaper.

## 1. Claimed but never executed

The most common shape by a wide margin. The code computes, names, or logs a
behavior that never actually runs, or a failure path returns success.

- **Withheld check:** exercise the path and assert its observable trace, not its
  presence — the count of calls, the sequence of intervals actually waited, the
  exit code on the failure branch, the request that reached the boundary.
- **Contract side:** whenever the contract requires a behavior, require the
  evidence that it executed. "Implement backoff" invites a computed number that
  is never used; "assert the waited sequence equals [...]" does not.

## 2. Gate present but not checking

A test, comparison, or verification entry point exists and passes while checking
nothing: empty inputs, a missing negative case, one interface standing in for
six, an assertion on shape instead of value.

- **Withheld check:** count the cases that actually reach the code under test
  with non-trivial input, and confirm the comparison covers values rather than
  only keys, lengths, or success flags.
- **Contract side:** state floors on what the gate must cover, and require an
  assertion on the coverage itself so emptying a case turns the gate red instead
  of silently weakening it.

## 3. Value claimed from the contract but hard-coded

Behavior documented as driven by configuration, schema, or contract is in fact a
literal in the source, or a placeholder stands in for a value that should have
been derived.

- **Withheld check:** mutate the contract or configuration and confirm the
  observable output changes with it. Search the source for the literal that
  should no longer exist.
- **Contract side:** require the mutation test as acceptance evidence, and name
  a zero-occurrence search for the literal.

## 4. Evidence asserted but not produced

The delivery record states that something was verified without carrying the
output that would show it, or promises an artifact the run never wrote.

- **Withheld check:** open the delivery record and the promised artifacts.
  Absence of the output is the finding; a conclusion is not evidence.
- **Contract side:** name the exact outputs to paste and the files to produce.
  Prefer "paste both outputs" over "verify and report".

## 5. Protection bypassable or test unstable

The gate can be routed around, or it passes only sometimes: a parallel race, an
alternate code path that skips the guard, a lock enforced by a command-line flag
rather than by the code.

- **Withheld check:** run the suite repeatedly and report the pass ratio rather
  than one green run. Try the bypass explicitly, and confirm a meta-check makes
  the bypass itself fail.
- **Contract side:** require a stated number of consecutive clean runs, and
  require the guard to be structural rather than dependent on how it is invoked.

## 6. Delivery hygiene

Work left uncommitted, a dirty tree, or a sensitive identifier left in a file
that simultaneously claims the identifier does not appear.

- **Withheld check:** confirm the tree is clean, that the claimed searches
  actually return zero, and that no artifact contradicts its own claim.
- **Contract side:** put a clean tree and the zero-occurrence searches in the
  acceptance evidence rather than trusting them as good practice.

## Keeping the library honest

A shape that stops finding anything has either been absorbed into the contract,
which is the desired outcome, or is being aimed at what the contract already
demanded. Check which, using the open and withheld results recorded per round in
[the review contract](review-contract.md). Add a shape only when a defect
escapes review twice for the same reason.
