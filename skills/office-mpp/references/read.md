# Reading MPP/MSPDI Files

## When to Use

User asks to parse, analyze, view, or extract data from .mpp or MSPDI .xml files.

## Workflow

1. **Detect format** — `.mpp` uses MPXJ (requires JVM), `.xml` uses ElementTree (pure Python)
2. **Read** — `mpp_reader.py` handles both formats transparently
3. **Output** — summary (default), JSON, tasks table, milestones, WBS tree, etc.

## Script Usage

```bash
python3 scripts/mpp_reader.py <file>              # full summary
python3 scripts/mpp_reader.py <file> --json        # structured JSON
python3 scripts/mpp_reader.py <file> --tasks       # task table
python3 scripts/mpp_reader.py <file> --wbs         # WBS tree view
python3 scripts/mpp_reader.py <file> --milestones  # milestones only
python3 scripts/mpp_reader.py <file> --critical-path
python3 scripts/mpp_reader.py <file> --overdue
python3 scripts/mpp_reader.py <file> --summary-level 2  # top 2 outline levels
```

## Common Analysis Patterns

| Pattern | Command | Use Case |
|---------|---------|----------|
| Project overview | `--summary` (default) | Quick health check |
| Milestone tracking | `--milestones` | SteerCo / status reports |
| Critical path | `--critical-path` | Identify schedule risks |
| WBS breakdown | `--wbs --summary-level 2` | High-level view for executives |
| Overdue tasks | `--overdue` | Action item identification |
| Full data export | `--json` | Feed into other tools / scripts |

## Output Format (JSON)

```json
{
  "project": { "title", "start", "finish", "last_saved", "author" },
  "tasks": [{ "uid", "id", "name", "wbs", "outline_level", "start", "finish",
               "duration", "percent_complete", "summary", "milestone", "critical", "notes" }],
  "resources": [{ "uid", "id", "name", "type" }],
  "assignments": [{ "uid", "task_uid", "resource_uid" }],
  "statistics": { "total_tasks", "leaf_tasks", "summary_tasks", "milestones",
                  "critical_path", "complete", "in_progress", "not_started", "overdue" }
}
```

## Large Files

For projects with >500 tasks, use `--summary-level N` to limit depth. Level 1 shows top-level workstreams only; level 2 adds sub-phases; level 3+ shows detailed tasks.

## Format Notes

- MPP files are binary (OLE2 Compound Document). Only MPXJ can read them.
- MSPDI XML files can be opened in any text editor. Namespace: `http://schemas.microsoft.com/project`.
- The reader never modifies input files.
