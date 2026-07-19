# GAP analysis

`mpp_plan_vs_actual.py` produces Plan vs Actual results for binary MPP and
MSPDI XML files. It supports explicit dates, weekly dates, JSON, Markdown, and
Excel output.

## Input behavior

- `.mpp`: read tasks through MPXJ. On each top-level workstream task, Number4
  supplies native Plan% and Number3 supplies native Gap% when present.
- `.xml`: read standard MSPDI task fields. Number4/Number3 are not mapped, so
  Plan%, Actual%, and Gap% are computed.
- Multiple files: concatenate their task streams before grouping. Workstream
  names are exact and duplicate top-level names are not safely merged; avoid
  duplicate workstream names across inputs.

## Calculation

A workstream is an OutlineLevel 1 task. Its calculation includes later
non-summary tasks with OutlineLevel greater than 1 until the next workstream.

For its leaf tasks:

```text
milestone_task = leaf task count
plan = count(finish <= cutoff at 17:00)
actual = sum(duration_hours * percent_complete / 100)
         / sum(duration_hours) * milestone_task
target_pct = round(plan / milestone_task * 100)
actual_pct = round(actual / milestone_task * 100)
gap = target_pct - actual_pct
```

When a binary MPP workstream has native Number4, its rounded value replaces
computed `target_pct`, the workstream's own PercentComplete becomes
`actual_pct`, and Number3 replaces `gap` when available. The result then has
`"source": "mpp"`; every other path has `"source": "computed"`.

## Commands

```bash
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.xml --date 2026-04-18
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --dates 2026-04-18,2026-04-25
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --json
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3 --excel gap.xlsx
```

Without a date option, use today's date. `--weeks N` starts with the Friday in
the current week and advances by seven days.

## JSON shape

```json
{
  "titles": ["Project title"],
  "dates": ["2026-04-18"],
  "results": [
    {
      "date": "2026-04-18",
      "workstreams": [
        {
          "project": "Workstream A",
          "target": "2026/05/01",
          "milestone_task": 2,
          "plan": 1,
          "actual": 1.67,
          "target_pct": 50,
          "actual_pct": 83,
          "gap": -33,
          "source": "computed"
        }
      ]
    }
  ]
}
```

JSON contains aggregate workstream results, not per-task details or separate
source fields for each metric.

## Excel output

Create a `Summary` sheet plus one sheet per cutoff date. Gap cells use red for
values at least 10, green for values at most -5, and yellow for other values
whose absolute value is at least 5.
