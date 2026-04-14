# GAP Analysis — Algorithm & Parameters

## Overview

`mpp_plan_vs_actual.py` generates a Plan vs Actual gap table in Board Meeting format. It supports single or multiple MPP/MSPDI files, date-series forecasting, and Excel output.

## GAP Calculation Algorithm

### Definitions

| Term | Definition |
|------|------------|
| **Workstream** | Top-level WBS item (OutlineLevel = 1) |
| **Leaf Task** | Task where `Summary = 0` (no children) |
| **Milestone Task** | Total leaf task count per workstream |
| **Plan (cutoff date)** | Leaf tasks where `Finish ≤ cutoff_date` |
| **Target%** | `Plan / Milestone Task × 100` |
| **Actual%** | Duration-weighted completion (see below) |
| **Gap%** | `Target% − Actual%` |

### Read-First Principle (§7.8)

Before computing, always check native MPP fields:

```python
# Priority 1: read from MPP custom fields
planned_pct = task.get("planned_pct")   # Number4 in .mpp / <Number4> in .xml
gap_pct     = task.get("gap_pct")       # Number3 in .mpp / <Number3> in .xml

if planned_pct is not None:
    source = "mpp"
else:
    source = "computed"
    planned_pct = compute_target_pct(tasks, cutoff)
```

Output always includes `"source": "mpp"` or `"source": "computed"` per field.

**Why this matters**: Project managers in XLSmart embed pre-reviewed Plan% and Gap% values in custom fields. Computing from schedule data can diverge by up to 40 percentage points from the PM-approved values (documented in exploration §7.8). Always prefer native fields.

### Duration-Weighted Actual%

When computing (no native field), never use a simple average of `%complete`:

```python
def compute_actual_pct(leaf_tasks):
    total_weight = sum(t["duration_hours"] for t in leaf_tasks)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(
        t["duration_hours"] * t["percent_complete"] / 100
        for t in leaf_tasks
    )
    # Scale to task-count space (same denominator as Target%)
    return (weighted_sum / total_weight) * len(leaf_tasks)
```

Leaf-only: summary tasks are excluded from all calculations.

## Parameters

### `--weeks N`

Generates N weekly forecast columns:
- Column 0: current (most recent past Friday or today)
- Columns 1..N-1: next N-1 Fridays

```bash
python3 mpp_plan_vs_actual.py project.mpp --weeks 3
# → columns: 2026-04-11, 2026-04-18, 2026-04-25
```

### `--dates DATE1,DATE2,...`

Explicit cutoff dates instead of auto-Friday series:

```bash
python3 mpp_plan_vs_actual.py project.mpp --dates 2026-04-18,2026-04-25,2026-05-02
```

### `--excel FILE`

Writes output to an Excel file (Board Meeting format):
- Sheet 1: Summary table (workstreams × dates, with color coding)
- Color: red = Gap > 10%, yellow = Gap 5-10%, green = Gap ≤ 5%

```bash
python3 mpp_plan_vs_actual.py project.mpp --weeks 3 --excel gap-report.xlsx
```

### `--json`

Outputs full structured data including per-task details:

```json
{
  "cutoff_date": "2026-04-18",
  "workstreams": [
    {
      "name": "Big Data Migration",
      "milestone_task": 42,
      "plan": 18,
      "target_pct": 42.86,
      "target_pct_source": "computed",
      "actual_pct": 38.10,
      "actual_pct_source": "mpp",
      "gap_pct": 4.76,
      "gap_pct_source": "mpp"
    }
  ]
}
```

## Multi-File Merge

When multiple files are provided, workstreams are merged by name:

```bash
python3 mpp_plan_vs_actual.py big-data.mpp genai.mpp
```

**Merge rules:**
1. Workstream names are matched case-insensitively after stripping common prefixes (e.g., "Phase 1 -")
2. Leaf tasks across all files are pooled per workstream
3. `Milestone Task` = total leaf count across all files for that workstream
4. Plan / Actual computed over the combined pool
5. Source is `"computed"` for merged workstreams (native fields not merged)

## Output Table Format (Markdown)

```
| Workstream         | Tasks | Target% | Actual% | Gap%   |
|--------------------|-------|---------|---------|--------|
| Big Data Migration |    42 |   42.9% |   38.1% |  4.8%  |
| GenAI Platform     |    28 |   32.1% |   28.6% |  3.5%  |
| **Total**          |    70 |   38.6% |   34.3% |  4.3%  |
```

## Integration with Board Meeting Slides

The `--excel` output matches the table structure in the XLSmart SteerCo template:
- Column headers: date strings (YYYY-MM-DD)
- Row headers: workstream names
- Values: Gap% with conditional color coding
- "Total" row at bottom with weighted average

Copy the `gap-report.xlsx` contents directly into the SteerCo deck slides.
