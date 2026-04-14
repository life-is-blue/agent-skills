# Generating Status/Todo Reports from Project Data

## When to Use

User wants to extract project status, milestones, action items, or blockers from a project plan and format as markdown.

## Workflow

1. **Read** — Parse MPP or MSPDI XML via `mpp_reader.py`
2. **Extract** — Pull workstream progress, milestones, overdue tasks, risk indicators
3. **Format** — Generate markdown tables matching `status.md` and `todo.md` structure

## Script Usage

```bash
# Status report (workstream progress + milestones + risks)
python3 scripts/mpp_report.py master-plan.mpp --status

# Todo report (active tasks + upcoming milestones + blockers)
python3 scripts/mpp_report.py master-plan.mpp --todo

# Both
python3 scripts/mpp_report.py master-plan.mpp --status --todo

# Raw data for custom formatting
python3 scripts/mpp_report.py master-plan.mpp --json
```

## Status Report Sections

### Project Overview
| Field | Source |
|-------|--------|
| Title | `ProjectProperties.Title` |
| Start / Finish | `ProjectProperties.StartDate / FinishDate` |
| Total / Leaf Tasks | Count from tasks list |
| Overdue | Leaf tasks past finish date with % < 100 |

### Workstream Progress
Top-level WBS items (OutlineLevel=1) with Start, Finish, PercentComplete, Critical flag.

### Milestones
All tasks where Milestone=1. Status determined by:
- **done**: PercentComplete >= 100
- **OVERDUE**: Past finish date and not complete
- **AT RISK**: Within 7 days of finish and < 50% complete
- **on track**: Otherwise

### Risk Indicators
- Overdue tasks (top 10 by finish date)
- Incomplete critical path tasks (top 10)

## Todo Report Sections

### Active Tasks
Non-complete leaf tasks sorted by finish date. Priority assigned by:
- **High**: Overdue or on critical path
- **Medium**: In progress (% > 0)
- **Normal**: Not started

### Upcoming Milestones
Milestones due within the next 30 days.

### Blockers / Overdue
Tasks past their finish date with days-overdue count.

## Field Mapping: MPP → Markdown

| MPP Task Field | Markdown Column |
|----------------|-----------------|
| Name | Task / Milestone |
| WBS | WBS |
| Finish | Target Date / Due Date |
| PercentComplete | % |
| Critical | Critical (Yes/blank) |
| computed | Status (on track / OVERDUE / AT RISK) |
| computed | Priority (High / Medium / Normal) |
| computed | Days Overdue |

## Integration with status.md / todo.md

The report output is designed as a **fragment** that can replace the corresponding sections in:
- `00-project-mgmt/status.md` — Current Status, Key Milestones, Risk tables
- `00-project-mgmt/todo.md` — Tasks, Milestones, Blockers tables

Copy the output and paste into the appropriate section of the target file.
