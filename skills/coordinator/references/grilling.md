# Grilling — the requirement interview

Interview the user persistently about their plan, decision, or idea until the
thinking is sharp, and capture what crystallizes as durable documentation: a
`CONTEXT.md` glossary and Architecture Decision Records. The interview is the
engine; the docs are the exhaust — both matter.

This is the Tier 1 tool: use it when direction or requirements are still
vague, before any implementation brief is written.

## The interview

Map the plan as a **design tree**: decisions branch into dependent decisions.
Process the tree in **rounds**, always targeting the **frontier** — the
decisions whose prerequisites are settled, i.e. the questions answerable now
without speculating on unsettled matters.

Each round:

1. Present the frontier questions **together**, each numbered and titled. The
   body may run multiple paragraphs with options; give a **recommended answer**
   for every question.
2. Gather environmental facts yourself — delegate investigation to sub-agents
   rather than asking the user for anything you could look up. While sub-agent
   reports are pending, keep asking the frontier questions that do not depend
   on them; only downstream questions wait.
3. Every answer reshapes the tree: settled decisions push the frontier outward
   and unblock the questions that depended on them.

Decisions belong to the user. Present each decision-type question and wait for
their answer; never settle a directional call on their behalf and move on.

The interview is done when the frontier is **empty**: every branch of the
design tree visited, nothing left silently assumed. Confirm the shared
understanding in a short recap before proceeding to any build step.

## The docs

Create files on demand — only when there is content to put in them.

**Glossary.** Keep a `CONTEXT.md` at the repo root (single-context repos), or a
`CONTEXT-MAP.md` indexing one `CONTEXT.md` per sub-area (multi-context repos).
The exact format is [context-format.md](context-format.md).
During the interview:

- Challenge terminology conflicts the moment they appear: "Your CONTEXT.md
  defines X as Y, but you seem to mean Z — which is correct?"
- Sharpen vague or overloaded terms into precise ones; ask clarifying
  questions to distinguish concepts the user is conflating.
- Stress-test domain relationships with concrete scenarios and edge cases;
  force explicit boundaries between concepts.
- Verify claims against the actual code and surface contradictions between
  stated behavior and implementation.
- Update `CONTEXT.md` **incrementally**, the moment a term resolves — never
  batch glossary work for the end.
- Keep `CONTEXT.md` totally devoid of implementation details. It is a
  glossary, nothing else.

**Decision records.** When the interview settles a decision that is hard to
reverse, surprising without context, *and* the result of a genuine trade-off,
record it as an ADR in `docs/adr/` per
[adr-format.md](adr-format.md). Skip the ADR when any of
the three conditions fails — most decisions do not deserve one.

## When the plan is sharp

A sharpened plan is not yet an executable brief. Return to the coordinator's
tier routing: single-round deliverables go to Tier 2
([brief-authoring.md](brief-authoring.md)); multi-round work goes to Tier 3
(the verified loop). Do not start implementing the plan inside the interview —
the deliverable here is a sharp plan plus its docs.

## Anti-patterns

- Asking the user a fact you could have grepped, measured, or delegated to a
  sub-agent.
- Asking questions whose answers depend on a decision not yet made — that is
  off-frontier speculation; wait for the frontier to reach them.
- Settling a directional decision yourself to keep momentum.
- Ending with "any other questions?" while branches of the tree remain
  unvisited.
- Writing ADRs for reversible, obvious, or uncontested decisions.
- Letting implementation details leak into `CONTEXT.md`.
- Batching glossary updates for "later" — later never comes.

## References

- [context-format.md](context-format.md) — the `CONTEXT.md` /
  `CONTEXT-MAP.md` glossary format.
- [adr-format.md](adr-format.md) — ADR naming, minimal template,
  and the three-condition threshold.
