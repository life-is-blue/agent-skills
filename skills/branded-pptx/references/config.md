# Spec reference

The generator takes one JSON file. Every field below is validated before a
single slide is written; anything the renderer cannot honour raises
`SPEC ERROR` and exit code 2.

## Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `title` | string | yes | cover title; `\n` starts a new line |
| `date` | string | no | replaces the template's auto-updating date field; omit to keep the field |
| `outline` | array | yes | one entry per page, in order |
| `output` | string | no | default output path; `--output` wins |
| `profile` | string | no | template profile path; `--profile` wins, then this, then `profiles/default.json` |

## Page entries

| Field | Type | Applies to | Meaning |
|---|---|---|---|
| `slide_type` | `"cover"` \| `"content"` | all | defaults to `"content"` |
| `title` | string | content | page title; required |
| `content_type` | string | content | `bullets` (default) \| `table` \| `columns` \| `mixed` \| `layout` |
| `content` | array | bullets, columns, mixed, layout | strings, or `{text, level, bold}` objects |
| `table` | object | table, mixed | `{headers: [...], rows: [[...], ...]}` |
| `columns` | number | columns | column count when `content` is a flat list; default 2 |
| `layout` | string | layout | template layout name, see [layouts.md](layouts.md) |
| `slots` | object | layout | `{"<placeholder idx>": "text"}`, overrides reading order |
| `images` | array | layout | image paths, filled into picture slots in reading order |

## content_type by example

### bullets — parallel statements

```json
{"slide_type": "content", "title": "核心能力",
 "content": ["统一数据接入", "秒级查询响应", {"text": "支持私有化部署", "bold": true}]}
```

Font size is the largest of 22/20/18/17/16/15pt that fits. More content than one
page holds is split onto `标题（续）` slides.

### table — comparison, parameters, metrics

```json
{"slide_type": "content", "title": "版本能力对比", "content_type": "table",
 "table": {"headers": ["能力", "标准版", "企业版"],
           "rows": [["检索方式", "关键词检索", "向量 + 关键词混合"],
                    ["并发", "100 QPS", "10000+ QPS"]]}}
```

Header row uses theme `accent1` on white. Every row must have exactly as many
cells as there are headers. Row capacity depends on the template's body height (about 12 rows on a 7.5in
slide); the rest paginate.

### columns — 2 to 4 parallel modules

```json
{"slide_type": "content", "title": "三个工作方向", "content_type": "columns", "columns": 3,
 "content": [
   {"title": "统一口径", "items": ["合并指标定义", "输出口径文档"]},
   {"title": "流程自动化", "items": ["核对环节脚本化", "异常自动告警"]},
   {"title": "结果可视化", "items": ["周报自动生成", "异常按人分派"]}]}
```

A flat `content` list is split evenly across `columns` instead.

### mixed — a claim plus its evidence

```json
{"slide_type": "content", "title": "下季度计划", "content_type": "mixed",
 "content": ["把方案推广到剩余两条业务线"],
 "table": {"headers": ["阶段", "时间", "交付物"],
           "rows": [["接入改造", "第 1-3 周", "两条线的数据接入"]]}}
```

Bullets take at most the top 40% of the body area, the table follows. If the
table does not fit, later rows continue on `标题（续）` table pages.

### layout — use a designed template page

```json
{"slide_type": "content", "title": "系统架构", "content_type": "layout",
 "layout": "<你的模板中的版式名>",
 "content": ["左侧模块标题", "右侧模块标题", "左侧说明", "右侧说明"],
 "images": ["arch-left.png", "arch-right.png"]}
```

Body slots fill in reading order (top to bottom, then left to right). When that
order is not what you want, address slots by index:

```json
{"slots": {"23": "左侧模块标题", "24": "左侧说明", "25": "右侧模块标题", "26": "右侧说明"}}
```

Run `python3 scripts/inspect_template.py --template T.pptx --layout "<名称>"` for
the indexes.
Picture slots with no image are removed rather than left as "click to add
picture" prompts, and the generator says so in its report.

## Errors you will see

| Message | Fix |
|---|---|
| `outline[N] uses content_type='table' but has no table.headers` | add the table, or use `bullets` |
| `outline[N].table.rows[M] has K cells but headers declare J` | pad or trim the row |
| `outline[N].layout='X' is not in the template` | `scripts/inspect_template.py --template T.pptx --layouts` |
| `slots reference placeholder idx [...] which layout 'X' does not have` | `scripts/inspect_template.py --template T.pptx --layout X` |
| `cover shape '...' is missing from ...` | the template was replaced; re-derive the profile with `--profile` |
| `PROFILE ERROR: ...` | the profile is missing or does not match its template; see SKILL.md "First use" |

## Verification findings

`verify_pptx.py` runs automatically after generation.

| Level | Finding | Meaning |
|---|---|---|
| error | `text ... needs about Xpt in a Ypt box` | text will overflow its box |
| error | `shape ... extends past the slide` | geometry leaves the canvas |
| error | `table ... ends Npt below the slide edge` | table too tall |
| error | `content slide has a title but no body content` | an empty page was produced |
| warning | `body area only N% filled` | below 22%; merge pages or add substance |
| warning | `body area N% filled` | above 95%; split the page |
| warning | `empty placeholder ... will render a prompt` | a layout slot got no content |
| warning | `table cell (rN,cM) needs about Xpt` | cell text will wrap past its row |

Errors mean the deck is wrong. Fix the spec and regenerate — do not hand over a
deck that still reports errors.
