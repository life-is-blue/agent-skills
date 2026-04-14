# Editing MSPDI XML Files

## When to Use

User asks to update task status, change dates, add or remove tasks in an existing project plan.

## Workflow

1. **Parse** — Read MSPDI XML with ElementTree
2. **Modify** — Apply requested changes
3. **Recalculate** — Update summary task rollups
4. **Validate** — Run structural checks
5. **Output** — Write to new file (never overwrite input)

## Script Usage

```bash
# Update task percent complete
python3 scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --percent-complete 90

# Update task finish date
python3 scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --name "Web Application" --finish "2026-04-20T17:00:00"

# Batch update from JSON
python3 scripts/mspdi_editor.py input.xml --output out.xml \
    --batch-update updates.json

# Delete task (and children + orphaned assignments)
python3 scripts/mspdi_editor.py input.xml --output out.xml \
    --delete-task --uid 5

# Add a new task
python3 scripts/mspdi_editor.py input.xml --output out.xml \
    --add-task --name "New Task" --outline-level 3 \
    --after-uid 5 --start "2026-04-15" --duration-days 5
```

## Critical Rules

### 1. Never modify the input file
Always write to `--output`. The original file is preserved as-is.

### 2. Preserve XML namespace
The namespace `http://schemas.microsoft.com/project` must be registered before parsing:
```python
ET.register_namespace('', 'http://schemas.microsoft.com/project')
```
Without this, output gets `ns0:` prefix pollution.

### 3. Recalculate summary rollups after changes
When child tasks are modified, parent summary tasks must be recalculated:
- **PercentComplete** = weighted average of children by duration
- **Start** = earliest child Start
- **Finish** = latest child Finish

### 4. Remove orphaned assignments when deleting tasks
When a task is deleted, any `<Assignment>` referencing that TaskUID must also be removed.

### 5. Delete cascades to children
Deleting a summary task also deletes all its children (tasks with deeper OutlineLevel).

## Batch Update JSON Format

```json
[
  { "uid": 5, "percent_complete": 90, "actual_start": "2026-04-01T08:00:00" },
  { "uid": 10, "finish": "2026-04-20T17:00:00", "notes": "Delayed by 1 week" },
  { "name": "Assessment", "percent_complete": 100, "actual_finish": "2026-04-10T17:00:00" }
]
```

Each entry must have `uid` and/or `name` to identify the task, plus fields to update.

## Updatable Fields

| JSON Key | MSPDI Element | Notes |
|----------|---------------|-------|
| `name` | `Name` | Task name |
| `start` | `Start` | ISO datetime |
| `finish` | `Finish` | ISO datetime |
| `duration_days` | `Duration` | Converted to PT format |
| `percent_complete` | `PercentComplete` | 0-100 |
| `actual_start` | `ActualStart` | ISO datetime |
| `actual_finish` | `ActualFinish` | ISO datetime |
| `notes` | `Notes` | Free text |
| `milestone` | `Milestone` | true/false |
| `critical` | `Critical` | true/false |

## Summary Task Recalculation Algorithm

```
for each summary task (bottom-up):
    children = direct children (outline_level == parent + 1)
    Start = min(child.Start for child in children)
    Finish = max(child.Finish for child in children)
    PercentComplete = sum(child.Duration * child.PercentComplete) / sum(child.Duration)
```
