# Routing: when to summon Gemini vs handle inline

The skill description covers the obvious cases. This file is for the borderline ones.

## Always route to Gemini

- User attached **any** image (screenshot, mock, Figma export, hand-drawn sketch).
- "Make a [page|component|landing|dashboard|hero|section]" from prose.
- "Build this in [React|Vue|Svelte|Tailwind|shadcn]" with a visual reference.
- "Convert this design to code" / "implement this UI".
- Visual polish requests: spacing, hierarchy, responsive breakpoints, color, typography, animation timing.
- Theming or design-system work: extracting tokens from a reference, applying a brand palette.

## Never route to Gemini

- Backend, API design, auth flows, database, infra.
- Build config debugging (Vite/Webpack/Next config errors) — Claude reads stack traces better.
- State management bugs (Redux/Zustand/Pinia), data-flow problems.
- Cross-file refactors with non-visual invariants ("rename this hook everywhere and update tests").
- Reading questions ("what does this component do?", "where is X defined?") — answer inline; routing here just adds latency.
- Tests (unit, integration, e2e) — Claude/Codex are better at test logic.

## Borderline — use judgment

| Situation | Lean toward |
|---|---|
| "Add a loading state to this component" | Gemini if visual (skeleton/shimmer). Inline if just `if (loading) return null`. |
| "Make this responsive" | Gemini. |
| "Fix this CSS bug" | Inline first. Route to Gemini if it needs visual judgment ("looks off"). |
| "Refactor this component" | Inline if structural/logical. Gemini if "make it cleaner visually". |
| "Add Tailwind classes for X" | Gemini. |
| "Set up Tailwind in this project" | Inline — it's config, not design. |
| "Storybook story for this component" | Inline — boilerplate, not design. |
| "Build a form" | Gemini for the layout; you wire up validation/submit after. |

## Mode selection within Gemini

- `design` — no existing target file in mind, you're producing something new.
- `implement` — there's a codebase, the design needs to fit existing conventions.
- `polish` — the file already exists and works; the request is "tweak it".

When unsure between `implement` and `polish`: if the brief contains a verb like "add", "build", "create" → `implement`. If it contains "tighten", "fix the spacing", "make it match", "less cramped" → `polish`.

## Multimodal handoff — the recurring failure mode

The failure that wastes the most value: user pastes a screenshot, the agent reads it (consuming the image into Claude's context), describes it in prose, then calls Gemini *without* `--ref`. Gemini now works from a lossy text description of an image it could have seen directly.

**Rule**: if the user's message has an image attachment, the very first Gemini call **must** include `--ref` for it. The agent's role is to forward, not to translate.
