# CONTEXT.md format

`CONTEXT.md` is the project's domain glossary: the shared vocabulary everyone
(and every agent) uses when talking about the work. It is a glossary and
nothing else — no implementation details, no architecture narrative.

## Structure

```markdown
# {Context name}

{1-2 sentences describing what this context covers.}

## {Term group, when clusters emerge}

### {Term}

{Definition, 1-2 sentences max. Define what it IS, not what it does.}

_Avoid_: {related words to stop using in favor of this term}
```

Rules:

- **Opinionated selection.** When several words exist for the same concept,
  pick the best one and record the losers under `_Avoid_`.
- **Tight definitions.** Two sentences maximum; essence, not behavior.
- **Domain terms only.** General programming concepts do not belong, even if
  the project uses them extensively.
- **Natural grouping.** Use subheadings when term clusters emerge; a flat list
  is fine for a cohesive area.

## Repository patterns

- **Single context** (most projects): one `CONTEXT.md` at the repo root,
  created lazily when the first term needs recording.
- **Multiple contexts**: a `CONTEXT-MAP.md` at the root listing each context,
  where its `CONTEXT.md` lives, and how the contexts relate. Read the map
  first to locate the right context, and infer which context applies to the
  topic at hand before writing.
