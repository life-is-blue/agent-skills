---
name: gemini-frontend
description: Use this skill whenever the user wants front-end design or implementation work — building/updating a page, component, landing page, dashboard, hero section; converting a screenshot/mock/Figma export into code; visual polish (spacing, hierarchy, responsive). Trigger eagerly when the user attaches an image, says "做一个 X 页面/组件", "实现这个设计", "前端实现一下", "改一下样式/间距/排版", or mentions Tailwind/shadcn/Material. Routes the work to Gemini CLI in headless mode because Gemini's multimodal vision and front-end code generation outperform Claude here.
allowed-tools: Bash, Read
argument-hint: "<design|implement|polish> \"<brief>\" [--ref <img>...] [--target <dir>] [--framework auto|react|vue|svelte|html] [--style auto|tailwind|css] [--read-only] [--stream] [--timeout 300]"
---

# Gemini Frontend Summon

Delegate front-end design and implementation to **Gemini CLI** in headless mode. Gemini's multimodal vision and UI code generation are stronger than Claude's for this slice; this skill is the well-paved path for invoking it.

## When to invoke (and when not to)

Invoke when **any** of these hold:
- User attached a screenshot, mock, Figma export, or any visual reference
- Request is a fresh design from prose ("做一个落地页", "design a pricing section")
- Request is integrating a design into existing front-end code
- Request is visual polish (spacing, hierarchy, responsive, animation, color)

Do **not** invoke for:
- Backend, API, auth, infra, complex state management
- Cross-file refactors with non-trivial invariants — Claude/Codex handle these better
- Pure questions about existing front-end code ("what does this hook do?") — answer inline
- Anything Claude can finish in one or two turns without visual judgment

The judgment call: if the task needs *visual taste* or *consumes an image*, route here. If it needs *system reasoning* across many files, don't.

## Three modes

| Mode | Input | Output |
|---|---|---|
| `design` | Brief (+ optional refs) | New standalone HTML/CSS or component files |
| `implement` | Brief + framework target (+ refs) | Edits integrated into existing codebase |
| `polish` | Existing files + concrete feedback | Surgical edits in place |

Pick `design` for greenfield, `implement` when there's a target codebase to integrate into, `polish` for tweaks to existing code.

## The multimodal rule (iron law)

If the user message contains an image (screenshot, mock, design reference) — **pass it to Gemini via `--ref`**. Do **not** read the image yourself first and describe it in the brief. Gemini's vision is the entire reason this skill exists; transcribing the image yourself defeats the purpose, wastes context, and loses fidelity.

Bad: "[reads mock.png] The design has a navy header with white text…" → invokes Gemini with that prose.
Good: invokes Gemini with `--ref mock.png` and lets it see the pixels.

**Corollary — no anchor, no launch.** If the task is purely visual (new design, visual polish, "make it prettier") and the user hasn't provided a reference image, **stop and ask** before calling Gemini. Either:

- "What look are you going for? Can you share a screenshot of a product whose UI you like?"
- Or list 2-3 concrete directions ("Vercel-ish / Linear-ish / Stripe-ish?") and have them pick.

Don't paper over the missing anchor by writing more words in the brief — words substitute badly for pixels, and Gemini will fill the gap with generic design-system defaults (see § "Constructing the brief" below for why this fails).

## Constructing the brief

Bad briefs produce bad output, and "bad brief" has a specific shape we've seen burn us. Rules:

### Forbidden vocabulary

These words are traps — they trigger automatic design-system machinery (contrast solvers, tonal palette generators, token systems) that override whatever brand/visual intent you stated:

- `Material`, `M3`, `MD3`, `Material Design 3`, `Expressive`
- `design token`, `seed color`, `tonal palette`, `color scheme`
- `state layer`, `surface tint`, `on-primary`
- `shape scale`, `emphasized easing`, `motion token`
- `HIG` (Apple), `Fluent` (Microsoft) — same class

If the user wants "the Google look," don't write "use M3 with seed X" — that's how brand colors get auto-darkened to "compliant" shades. Pass a Google product screenshot via `--ref` and let Gemini see it.

### Preferred vocabulary

- Concrete visual references via `--ref` (1-3 images; current state + desired direction).
- Literal hex values: `primary: #f19132, text on primary: #1c1816`.
- Taste words that describe *feel*, not systems: "工具 SaaS 气质", "紧凑密度", "锐利现代感", "活力", "克制".
- Product-name anchors when an image isn't available: "Linear-ish", "Raycast-ish", "shadcn demo". These are ambiguous enough that Gemini keeps visual judgment in its court, not in its token solver.

### Rollback vs refactor vs greenfield

| The work is really… | Mode | Brief shape |
|---|---|---|
| "Current version is wrong direction, here's what I want instead" | `polish` (if structure stays) or `implement` (if CSS system needs ripping out) | Pass both **current** and **target** references. Name what to *delete* explicitly (e.g. "delete all `--md-sys-color-*` variables") — polish mode will not uproot a variable system on its own. |
| "Add/integrate a new screen into existing app" | `implement` | Framework, style system, existing components to reuse, constraints. |
| "From scratch" | `design` | Feel + references. Don't prescribe the DOM structure. |

### Hard constraints always go in the brief

API paths, file field names, file size limits, i18n key names, "don't touch `tests/`" — Gemini will helpfully refactor these unless you pin them. Write a numbered list inside the brief.

## Calling the helper

```bash
scripts/gemini-summon.sh <mode> "<brief>" [flags]
```

Flags:
- `--ref <path>` — multimodal reference (image or file). Repeatable. Translated into Gemini's native `@path` syntax.
- `--target <path>` — working directory; helper `cd`s here before calling Gemini. Default: current dir.
- `--framework auto|react|vue|svelte|html` — auto-detected from `package.json` if `auto`.
- `--style auto|tailwind|css|styled` — auto-detected from `tailwind.config.*` / deps if `auto`.
- `--read-only` — drops `--yolo`; Gemini will only propose, not write.
- `--stream` — live timeline to stderr (tool calls, file edits, final stats) + full NDJSON captured to `/tmp/gemini-summon-*.ndjson`. Use for `design`/`implement` runs that may take > 30s; skip for short `--read-only` reviews.
- `--timeout <sec>` — default 300.
- `--model <name>` — passthrough to `gemini -m`. Leave unset by default.
- `--raw` — emit Gemini's full JSON output instead of the human summary (for debugging).

**Status / follow** (for inspecting live or recent runs):

```bash
scripts/gemini-summon.sh --status              # list recent stream sessions with stats
scripts/gemini-summon.sh --follow latest       # tail -f the most recent session, formatted
scripts/gemini-summon.sh --follow <path.ndjson>
```

The helper is **yolo by default** (auto-writes files). Front-end edits are reversible via `git restore`.

## What the helper does

1. **Precheck**: `command -v gemini`. If missing, prints install instructions (`npm install -g @google/gemini-cli`) and exits 127.
2. **Auto-detect** framework and style system from the target directory.
3. **Build prompt** with a mode-specific system prefix + the user's brief + `@path` references.
4. **Invoke** `gemini -p "<prompt>" -o json --yolo` (or without yolo for `--read-only`) under `timeout`.
5. **Parse** JSON output, surface `error` field if present, otherwise print Gemini's `response` plus a one-line stat header.

See `references/headless-output.md` for the JSON schema and error handling.

## What you do *after* Gemini returns

Branch on whether Gemini wrote files or only produced text — they need different follow-ups.

### If `yolo=on` (write modes — `design`/`implement`/`polish` without `--read-only`)

Gemini already wrote to disk. Your job is **verification, not narration**:

1. `git diff --stat` — see which files changed.
2. `git diff <file>` for any change that looks larger than expected. Don't read everything reflexively.
3. If the project has a dev server (`npm run dev`/`bun dev`/`pnpm dev`), tell the user the command — don't auto-start it (port conflicts, blocking).
4. Summarize in **one paragraph**: what changed, what to look at first, suggested next iteration.

Do **not** re-paraphrase Gemini's response prose — the helper already printed it and the actual deliverable is the diff.

### If `yolo=off` (`--read-only` — review, critique, audit)

Nothing was written. Gemini's response **is the deliverable**. Your job is to **make it actionable**:

1. Reorganize Gemini's prose into a priority ladder (P0 / P1 / P2, or "must / should / nice").
2. For each item, point at the concrete file + line where it applies (read the relevant file if you need to confirm the line number — but don't go fishing).
3. End with a clear next-step menu: "want me to land P0 only? P0+P1? all of it?"

Restructuring and concretizing the analysis is the value-add — that's not duplication, that's the work.

### Always
- Don't loop back into Gemini for a second pass on the same turn. Return to the user, let them give the next brief.
- Don't open every changed file just to "make sure".

## Examples

```bash
# Design from scratch with a mock
scripts/gemini-summon.sh design "Pricing page, 3 tiers, modern SaaS feel" --ref ./mocks/pricing.png

# Implement a Figma screen into the React app
scripts/gemini-summon.sh implement "Build the dashboard header per the mock; reuse existing Button component" \
  --ref ./design/header.png --target ./apps/web

# Polish: tighten spacing
scripts/gemini-summon.sh polish "Header padding feels cramped on mobile; tighten desktop too. Match the spacing of the cards section below."

# Read-only: get a diff proposal without writing
scripts/gemini-summon.sh implement "Refactor Card to support a leading icon slot" --target ./src --read-only

# Long-running design run with live timeline visible in stderr
scripts/gemini-summon.sh design "Full marketing landing page with 5 sections" --ref ./mock.png --stream
```

## Anti-patterns

- User attached an image and you didn't pass `--ref` for it.
- You read the image first to "understand" before calling Gemini.
- Task is purely visual and there's no `--ref` at all — you wrote a wall of text instead of asking the user for a reference or a direction.
- You put design-system vocabulary in the brief (`Material`, `M3`, `design token`, `seed color`, `state layer`, `shape scale`…). See `references/antipatterns/case-01-design-token-trap.md` for the real failure this caused.
- You asked Gemini to "use brand color X as primary" **without** also telling it to delete the existing computed color variable system. Polish re-colors inside the system; it doesn't remove it.
- You used this for a backend task because "Gemini is faster" — wrong tool.
- In `yolo=on` mode, you re-narrated Gemini's prose instead of reporting on the diff.
- In `--read-only` mode, you handed back Gemini's wall of text unchanged instead of restructuring it into a priority ladder with file pointers.
- You looped Gemini ≥ 2 times in one turn instead of returning to the user.
- You auto-started the dev server and blocked the session.
- You added `--model` without the user asking — the default model is the right pick.

## References

- `references/routing.md` — fuller decision tree for borderline cases.
- `references/headless-output.md` — Gemini headless JSON schema + error handling.
- `references/antipatterns/` — archived failures with before-images and root-cause notes. Read when a run goes sideways.
