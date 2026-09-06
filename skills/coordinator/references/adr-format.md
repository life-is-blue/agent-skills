# ADR format

Architecture Decision Records live in `docs/adr/`, numbered sequentially:
`0001-slug.md`, `0002-slug.md`, … Create the directory only when the first ADR
needs it. To assign a number, scan the directory for the highest existing
number and increment by one.

## Minimal template

```markdown
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

An ADR can be a single paragraph. The value is in recording *that* a decision
was made and *why*, not in ceremony.

## Optional additions

Add these only when genuinely useful:

- **Status** frontmatter: `proposed | accepted | deprecated | superseded by ADR-NNNN`
- **Considered Options** — when rejected alternatives are worth remembering
- **Consequences** — when the decision has non-obvious downstream effects

## When to write one

All three conditions must hold:

1. **Hard to reverse** — meaningful cost to changing course later.
2. **Surprising without context** — a future reader will wonder "why on earth…".
3. **Result of a trade-off** — genuine alternatives existed and one was chosen
   deliberately.

Decisions that qualify include: architectural topology, integration patterns
between contexts, technology choices with vendor lock-in, scope boundaries,
deliberate deviations from convention, invisible constraints, and non-obvious
rejections of alternatives.

Skip the ADR for reversible, obvious, or uncontested decisions.
