# Using your template's layouts

A corporate template is mostly a layout library — picture grids, left-right
splits, chart pages, section dividers. `content_type: "layout"` puts a page on
one of those instead of drawing text boxes over a blank one, which is the
difference between a deck that looks designed and one that looks assembled.

Layout names, indexes and geometry are template state, not code. Read them from
your own template; nothing here is hard-coded.

## Inventory your template first

```bash
python3 scripts/inspect_template.py --template templates/template.pptx --layouts
```

```
template.pptx: 13.33 x 7.5in, 4 sample slides, 29 unique layouts
  <layout name>        bodies=7   pictures=1   charts=0
  ...
```

Then look at one in detail — this is the list of slots you fill:

```bash
python3 scripts/inspect_template.py --template templates/template.pptx --layout "<name>"
```

```
<name> (master 0)
  idx=15  BODY     (0.46, 0.36) 6.95x0.79in  <- page title
  idx=37  BODY     (0.47, 2.55) 2.06x0.49in
  idx=32  BODY     (0.47, 3.10) 3.25x0.84in
  idx=11  PICTURE  (5.42, 1.35) 6.89x4.19in
```

Worth recording for each layout you plan to use: how many picture slots it has,
the body slot indexes in reading order, and the first picture's aspect ratio so
you can crop assets to fit.

## Filling one

```json
{"slide_type": "content", "title": "系统架构", "content_type": "layout",
 "layout": "<name>",
 "content": ["模块一", "模块二", "模块一说明", "模块二说明"],
 "images": ["arch.png"]}
```

`content` fills body slots in **reading order** — top to bottom, then left to
right. For paired layouts that usually means all the headings first, then all
the descriptions. When that is not what you want, address slots by index:

```json
{"slots": {"23": "左侧标题", "24": "左侧说明", "25": "右侧标题", "26": "右侧说明"}}
```

`images` fills picture slots in the same reading order.

## Picking one

| Situation | Look for |
|---|---|
| one diagram plus explanation | 1 picture, several body slots |
| one screenshot, minimal text | 1 full-width picture, 1 body slot |
| before / after, two products | 2 pictures, 4 body slots |
| three or four parallel cases | 3–4 pictures with paired caption slots |
| a photo wall or logo wall | 6+ pictures, no body slots |
| a chart beside its takeaways | a chart placeholder plus left-hand body slots |

## Rules the generator applies

- **The title slot is not always `idx=15`.** Templates renumber it — and a
  layout may even use 15 for a *picture*. Title resolution checks the
  placeholder type first, then the profile's index, then falls back to the
  topmost wide text slot in the title band. Never put the page title in `slots`.
- **Picture slots with no image are deleted**, so a deck never ships with
  "click to add picture" prompts. Every deletion is reported.
- **A layout that could only produce a title on an empty page is rejected.** If
  a picture-only layout gets no `images`, that is a `SpecError`, not a blank
  slide.
- **Chart placeholders cannot hold a native chart here.** Render the chart to
  PNG and pass it in `images`; the placeholder is swapped for a picture at the
  same geometry.
- **Layout names match exactly**, including full-width characters. An unknown
  name raises a `SpecError` that tells you how to list the valid ones.

## After a template update

Re-run `--layouts`, and re-derive the profile with
`--profile > profiles/default.json`. The generator fails loudly when a name or
index it needs no longer resolves, so a stale profile shows up immediately
rather than as a silently misplaced title.
