---
name: office-mpp
description: "Read, analyze, track, export, create, or edit Microsoft Project plans (.mpp, .xml / MSPDI). Use when the user asks to open a project plan, check schedule progress, generate a Plan vs Actual gap table, export a Gantt / review spreadsheet to Excel, create a new MSPDI timeline, or update task dates and completion in an existing plan. Triggers on: 项目进度, Microsoft Project, .mpp, MSPDI, Plan vs Actual, gap analysis, 甘特图, Gantt, 里程碑, milestone, WBS, baseline, schedule variance, 进度追踪, Excel 审视表, project schedule, timeline, 项目计划, 进度报告, 甘特图导出, 里程碑追踪, task completion, percent complete."
license: MIT
metadata:
  version: "1.0"
  category: productivity
  sources:
    - Microsoft Project MSPDI XML Schema (http://schemas.microsoft.com/project)
    - MPXJ Library (https://www.mpxj.org)
    - OpenXML / openpyxl for Excel export
---

# office-mpp Skill

Handle the request directly. Do NOT spawn sub-agents. Always write the output file the user requests.

Before first use: `bash SKILL_DIR/scripts/env_check.sh`

## Task Routing

### Tracking (READ / GAP / EXPORT)

| Task | Script | Reference |
|------|--------|-----------|
| **READ** — parse, summarize, extract tasks / milestones | `mpp_reader.py` | `references/read.md` |
| **GAP** — Plan vs Actual gap table (Board Meeting format) | `mpp_plan_vs_actual.py` | `references/gap.md` |
| **EXPORT** — MPP/XML → Excel review spreadsheet + Gantt | `mpp_to_excel.py` | `references/export.md` |

### Authoring (CREATE / EDIT / VALIDATE)

| Task | Script | Reference |
|------|--------|-----------|
| **CREATE** — new MSPDI XML from scratch or JSON spec | `mspdi_create.py` | `references/create.md` |
| **EDIT** — update tasks, dates, % in existing MSPDI XML | `mspdi_editor.py` | `references/edit.md` |
| **VALIDATE** — 8-rule structural check | `mspdi_validate.py` | `references/mspdi-schema.md` |

---

## READ — Parse project plan

```bash
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp                    # full summary
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --json             # structured JSON
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --tasks            # task table
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --milestones       # milestones only
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --critical-path    # critical path tasks
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --resources        # resource list
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --wbs              # WBS tree view
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --overdue          # tasks past due
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --summary-level 2  # WBS depth limit
```

Supports both `.mpp` (MPXJ + JVM required) and `.xml` MSPDI (pure Python). The reader never modifies source files.

**Additional flags:**
- `--resources` — List all resources with type and ID
- `--wbs` — Show hierarchical WBS tree view

---

## GAP — Plan vs Actual analysis

```bash
# Single file, current date
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp

# Multiple files merged (workstreams combined)
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py bd.mpp genai.mpp

# Weekly forecast: this week + N-1 future Fridays
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3

# Single specific date
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --date 2026-04-18

# Specific cutoff dates (multiple)
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --dates 2026-04-18,2026-04-25

# Excel output (Board Meeting format)
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3 --excel gap.xlsx

# JSON for downstream processing
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --json
```

**CRITICAL — GAP RULES:**

1. **读优先 (Read-first)**: Read `Number4` (Plan%) and `Number3` (Gap%) from MPP native fields. Fall back to computation only when fields are absent. Output marks `"source": "mpp"` vs `"source": "computed"` for each value.
2. **Leaf tasks only** for Milestone Task count (summary tasks excluded).
3. **Duration-weighted Actual**: `sum(duration_hours × %complete) / total_duration_hours × leaf_count`. Never simple average.
4. **Never recompute if native fields exist** — §7.8 of `xlsmart-project/04-tech-research/tech-proposals/ai-project-management-practices-exploration.md` documents up to 40-point divergence when ignoring MPP fields.

See `references/gap.md` for algorithm details, `--weeks`/`--dates`/workstream merge logic.

---

## EXPORT — MPP → Excel review spreadsheet

```bash
# Auto-named alongside input
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp

# Explicit output
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --output review.xlsx

# Subset of sheets
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --sheets overview,overdue

# Deep analysis mode
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --analyze
```

**CRITICAL — EXPORT RULES:**

1. **Cell-fill Gantt only** — no chart objects. WPS and Google Sheets fail to render chart-based Gantt.
2. **No hardcoded outline levels** — discover task hierarchy from the data; never assume max depth.
3. **Leaf tasks only** are subject to overdue marking (summary rows excluded from overdue coloring).
4. `--sheets` opts in to named subset; default produces all 4 sheets + Gantt tab.

Default sheets: `overview`, `tasks`, `overdue`, `workstreams`. Gantt is always appended.

**Additional flags:**
- `--analyze` — Deep analysis mode with additional diagnostics

---

## CREATE — New MSPDI XML

```bash
# Minimal plan
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --title "My Project" --start 2026-04-15

# From JSON spec (tasks, resources, assignments)
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --from-json spec.json

# From custom template
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --from-template custom.xml --title "New"
```

See `references/create.md` for JSON spec schema and phased plan patterns.

---

## EDIT — Modify existing MSPDI XML

```bash
# Update by UID
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --percent-complete 90

# Update by name
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --name "Web App" --finish "2026-04-20T17:00:00"

# Update task name
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --task-name "New Task Name"

# Update actual start/finish dates
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --actual-start "2026-04-15T08:00:00" --actual-finish "2026-04-20T17:00:00"

# Batch update from JSON
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --batch-update updates.json

# Delete a task (cascades to children + orphaned assignments)
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml --delete-task --uid 5

# Add a new task
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --add-task --name "New Task" --outline-level 3 --after-uid 5 \
    --start "2026-04-15" --duration-days 5
```

**CRITICAL — EDIT INTEGRITY RULES:**

1. **Never modify input** — always write to `--output`. Original file is preserved.
2. **Pre-write validate** — the editor runs `mspdi_validate` on the output buffer before writing. If invalid, exits 1 with `E_INPUT:` prefix; no file is written.
3. **Atomic write** — output is written to `<path>.tmp` then `os.replace()`. Interrupted runs never leave half-written files.
4. **Preserve namespace** `http://schemas.microsoft.com/project`. Register before parse; verify output is namespace-clean.
5. **Resolve `--name` to UID internally** — logs `resolved name="X" to uid=N` on stderr for agent verification.

**Additional flags:**
- `--task-name` — Rename a task (alternative to inline --name in updates)
- `--actual-start`, `--actual-finish` — Set actual start/finish dates for progress tracking

---

## VALIDATE — Structural check

```bash
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml           # human-readable
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml --json    # machine-readable
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml --fix --output fixed.xml  # auto-fix
```

8 validation rules: structure, UID uniqueness, WBS consistency, date logic, percentage range, assignment integrity, calendar references, duration format.

---

## Key Invariants

1. **MSPDI XML is the editable format** — MPP is binary read-only. All writes target MSPDI XML.
2. **UID uniqueness** — Task / Resource / Assignment UIDs must be unique within a file.
3. **Summary rollup** — Parent summary fields (`Start`, `Finish`, `PercentComplete`) are computed from children; never set directly.
4. **Namespace** — Always `http://schemas.microsoft.com/project`. Never omit or alias.
5. **Duration format** — `PT###H##M##S` (e.g., `PT760H0M0S` = 95 work-days × 8h).
6. **Critical field** — Task `critical` boolean indicates tasks on the critical path. Read from MPP Number4/Number3 fields or computed by MPP engine.
7. **Source tracking** — All tasks include `planned_pct_source` and `gap_pct_source` fields marking whether values came from MPP native fields ("mpp") or were computed ("computed").

---

## Exit Codes & stderr Prefixes

| Code | Prefix | Meaning | Agent Action |
|------|--------|---------|--------------|
| `0` | — | Success | Continue |
| `1` | `E_INPUT:` | Input / validation error | Fix args; do not retry identically |
| `2` | `E_ENV:` | Dependency missing | Run `env_check.sh --json`, apply fix commands |
| `2` | `E_IO:` | I/O error | Check path writability; retry may work |

**Parsing rule for agents**: `E_*:` prefix must appear as the **first line of stderr**, on its own line. Strip it before presenting to the user.

---

## Maintenance Scripts

REPORT, DIFF, CONVERT, and ANALYZE scripts are not primary Skill operations. Usage guides are in `references/maintenance.md`.

---

## Utility Scripts

```bash
python3 SKILL_DIR/scripts/mpp_reader.py file.mpp                        # read / parse
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py file.mpp --weeks 3      # gap analysis
python3 SKILL_DIR/scripts/mpp_to_excel.py file.mpp --output out.xlsx    # export to Excel
python3 SKILL_DIR/scripts/mspdi_create.py --output new.xml --from-json  # create plan
python3 SKILL_DIR/scripts/mspdi_editor.py in.xml --output out.xml ...   # edit plan
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml --json             # validate
python3 SKILL_DIR/scripts/mpp_report.py file.mpp --status --todo        # status / todo report
python3 SKILL_DIR/scripts/mpp_diff.py old.xml new.xml -o diff.md        # version diff
python3 SKILL_DIR/scripts/mpp_converter.py ./mpp-dir/ --output-dir out/ # batch convert
python3 SKILL_DIR/scripts/mpp_analyze.py file.xml --json                # deep analysis
bash   SKILL_DIR/scripts/env_check.sh --json                            # env check
```

