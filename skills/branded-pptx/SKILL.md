---
name: branded-pptx
description: "Build a PowerPoint deck from an outline on the organisation's own .pptx template, with automatic layout verification. Use when the user asks for a 对外 deck, customer proposal, project report, solution overview, QBR, or wants an outline turned into slides that match a corporate template. Triggers on: 对外 PPT, 汇报 PPT, 客户提案, 解决方案介绍, 项目汇报, 演示文稿, 幻灯片, 制作 PPT, 生成 PPT, 模板 PPT, 标准模板, corporate deck, branded slides, pptx, slides, presentation, template deck."
---

# branded-pptx

Turns an outline into a deck built on **your** template: real slides copied from
it, real layouts, real theme colours and fonts. The rendering engine is
template-agnostic — the few facts about a specific template live in a profile
under `profiles/`. Handle the request directly; do not spawn sub-agents.

Requires `python-pptx` (`python3 -c "import pptx"`). LibreOffice is optional and
only used for visual verification.

**No template is distributed with this Skill.** Templates are corporate assets;
supply your own before first use.

## First use: create a profile

```bash
cp /path/to/corporate.pptx SKILL_DIR/templates/<your-template>.pptx
python3 SKILL_DIR/scripts/inspect_template.py \
  --template SKILL_DIR/templates/<your-template>.pptx --profile \
  > SKILL_DIR/profiles/default.json
```

Detection is a heuristic — **read the result before using it**. It records which
slide is the cover, what its title and date shapes are called, how far right the
title may run before it hits the artwork, which layout content pages use, and
where the body area starts and ends. Field meanings are in
`scripts/deckprofile.py`; `profiles/example.json` shows the shape of the file.
Both templates and local profiles are gitignored.

## Workflow

1. **Write a spec.** JSON, one entry per page. Start from
   `python3 SKILL_DIR/scripts/generate_deck.py --example`.
2. **Generate.** `python3 SKILL_DIR/scripts/generate_deck.py spec.json --output deck.pptx`
3. **Read the layout report.** The generator runs `verify_pptx.py` automatically
   and prints every finding. **Errors are real defects — fix the spec and
   regenerate.** Never report success while errors are printed.
4. **Look at it if you can.** When LibreOffice is available, rasterise and read
   the images before handing the deck over:
   `python3 SKILL_DIR/scripts/verify_pptx.py deck.pptx --render out/`

Exit codes: `2` the spec cannot be rendered faithfully, `3` the profile is
missing or does not match its template, `1` the deck has layout errors.

## Commands

| Command | Purpose |
|---|---|
| `scripts/generate_deck.py spec.json --output deck.pptx` | build the deck, then self-check |
| `scripts/generate_deck.py --example` | print a working example spec |
| `scripts/generate_deck.py ... --profile profiles/other.json` | build on a different template |
| `scripts/verify_pptx.py deck.pptx [--render DIR]` | re-check, optionally rasterise to PNG |
| `scripts/inspect_template.py --template T.pptx --profile` | derive a draft profile |
| `scripts/inspect_template.py --template T.pptx --layouts` | list the template's layouts |
| `scripts/inspect_template.py --template T.pptx --layout NAME` | placeholder geometry of one layout |
| `scripts/inspect_template.py --template T.pptx --slides --theme` | sample slides, theme colours and fonts |

## Spec shape

```json
{
  "title": "项目名称\n季度汇报",
  "date": "2026年4月1日",
  "outline": [
    {"slide_type": "cover"},
    {"slide_type": "content", "title": "核心进展", "content": ["要点 1", "要点 2"]},
    {"slide_type": "content", "title": "指标对比", "content_type": "table",
     "table": {"headers": ["指标", "上季度", "本季度"],
               "rows": [["处理时长", "40 分钟", "4 分钟"]]}}
  ]
}
```

`title` is the cover title (`\n` splits lines). Full field reference, every
`content_type`, and worked examples: [references/config.md](references/config.md).

## Choosing the page form

| Content | `content_type` | Notes |
|---|---|---|
| 3–5 parallel statements | `bullets` (default) | plain list; the weakest option — prefer another form when the content allows |
| comparison, parameters, metrics | `table` | needs `table.headers` + `table.rows` |
| 2–4 parallel modules | `columns` | `content` is a list of `{title, items}` |
| a claim plus supporting data | `mixed` | bullets above, table below |
| anything that wants pictures | `layout` | uses a real layout from your template |

A corporate template usually carries a designed layout library — picture grids,
left-right splits, chart pages. When a page has images or a diagram, use
`content_type: "layout"` instead of drawing text boxes. How to inventory and
pick one: [references/layouts.md](references/layouts.md).

## What the generator enforces, and what it does not

Enforced in code, so you can rely on it:

- **Cover title** — one font size and one paragraph style for every line; the
  size drops from 36pt through 24pt until the longest line fits the profile's
  safe width; below 24pt the box switches to wrap mode rather than growing over
  the artwork. Alignment and position stay exactly as the template has them.
- **Overflow** — bullets and tables are measured before writing. Body text takes
  the largest size that fits (22→15pt), and anything left over moves to a
  `（续）` continuation slide.
- **Brand** — table headers and column titles use theme colour `accent1`; body
  text inherits the theme font. No hard-coded RGB or font names.
- **Failures are loud** — a `table` page with no table, an unknown layout name,
  or a ragged table raises `SpecError` instead of emitting a blank slide.

Not enforced — your judgement, checked only as warnings:

- **Density.** `verify_pptx.py` warns below 22% and above 95% fill. A 12%-filled
  page usually means the content should merge with its neighbour.
- **Whether a page deserves a picture.** The verifier cannot tell.
- **Content quality.** Below.

## Content rules for external decks

- One idea per slide; the title states the conclusion, not the topic.
- Quantify: "查询 30s → 3s" beats "性能大幅提升".
- Expand an abbreviation on first use.
- **Before delivering, scan for internal IPs, hostnames, credentials,
  unannounced customer names, and unreleased roadmap items.** Assume the deck
  leaves the company. Check the file's own metadata too — `dc:creator` and
  `cp:lastModifiedBy` are inherited from the template and often carry a real
  person's name.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `PROFILE ERROR: no template profile selected` | first use — follow "First use" above |
| `PROFILE ERROR: points at a template that does not exist` | copy the template in, or fix `template` in the profile |
| `cover shape '...' is missing from ...` | the template changed — re-derive the profile |
| `SPEC ERROR: ... is not in the template` | layout name typo — `inspect_template.py --layouts` |
| `ERROR ... extends past the slide` | text too long for its box; shorten it or split the page |
| `empty placeholder ... will render a prompt` | a layout slot got no content; supply it or pick a smaller layout |
| Fonts look wrong when opened | the template's brand font is not installed locally; the file is still correct |
