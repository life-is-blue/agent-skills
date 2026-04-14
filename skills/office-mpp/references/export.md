# EXPORT — MPP/MSPDI to Excel

Convert project plan files to Excel review spreadsheets with structured sheets and visual formatting.

## Quick Start

```bash
# Basic — auto-names output alongside input
python3 scripts/mpp_to_excel.py project.mpp

# Explicit output path
python3 scripts/mpp_to_excel.py project.mpp --output /path/to/review.xlsx

# Selected sheets only
python3 scripts/mpp_to_excel.py project.mpp --sheets overview,overdue
```

## Output Sheets

### Overview

Project metadata + workstream progress:
- Project info: title, date range, task counts (total / summary / leaf / overdue)
- Level 1 workstreams: name, %, start, finish
- Level 2 phases: name, %, parent workstream

### All Tasks

Full task list (all tasks) with:
- Columns: UID, WBS, Name (indented by outline level), Level, Summary flag, Start, Finish, %, Critical, Milestone, Duration
- Color coding: red = overdue leaf, yellow = summary, green = completed
- Auto-filter enabled on all columns

### Overdue

Overdue leaf tasks only (summary excluded):
- Sorted by due date ascending
- Columns: UID, WBS, Task, Due Date, %, Days Overdue
- All rows highlighted red

### Workstreams

Summary tasks at Level 1-3:
- Bold formatting for Level 1-2
- Indented names by level
- Shows % complete, date range, critical flag

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `<input-basename>.xlsx` | Output file path |
| `--sheets` | `all` | Comma-separated: `overview`, `tasks`, `overdue`, `workstreams` |

## Auto-Naming

When `--output` is omitted, the script generates the output filename from the input:
- `project.mpp` → `project.xlsx`
- `JUDO Timeline 0409(aws:gcp:classAI).mpp` → `JUDO Timeline 0409(aws-gcp-classAI).xlsx`

Colons (`:`) are replaced with hyphens (`-`) for filesystem compatibility.

## Dependencies

- `openpyxl` — `pip3 install openpyxl`
- `mpp_reader.py` — for parsing input (auto-imported from same directory)
- For `.mpp` files: MPXJ + JRE (same as READ task)
- For `.xml` files: pure Python (ElementTree)
