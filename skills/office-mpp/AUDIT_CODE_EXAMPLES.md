# office-mpp Audit — Code Examples & Detailed Findings

## Issue #1: schema.py Missing `critical` Field

### The Problem

**schema.py** (lines 18-50) defines the Task dataclass WITHOUT a `critical` field:

```python
@dataclass
class Task:
    uid: int
    id: int
    name: str
    start: str = ""
    finish: str = ""
    duration: str = ""
    percent_complete: float = 0.0
    outline_level: int = 0
    summary: bool = False
    milestone: bool = False
    # ... other fields but NO "critical" field
```

**BUT mpp_reader.py** (_read_mpp, line 66) DOES return it:

```python
task_data = {
    "uid": int(str(t.getUniqueID())) if t.getUniqueID() else 0,
    # ... other fields ...
    "critical": bool(t.getCritical()) if t.getCritical() is not None else False,
    # ↑ THIS FIELD IS RETURNED BUT NOT IN schema.py
    "notes": str(t.getNotes() or ""),
    # ...
}
```

**AND mpp_reader.py** (_read_xml, line 133) ALSO returns it:

```python
task_data = {
    "uid": get_int(task_elem, "UID"),
    # ... other fields ...
    "summary": get_int(task_elem, "Summary") == 1,
    "milestone": get_int(task_elem, "Milestone") == 1,
    "critical": get_int(task_elem, "Critical") == 1,
    # ↑ THIS FIELD IS RETURNED BUT NOT IN schema.py
    "notes": get_text(task_elem, "Notes"),
    # ...
}
```

### Fix

Add to schema.py Task dataclass (after `milestone` field):

```python
critical: bool = False
```

---

## Issue #2: schema.py Missing `duration_hours` Field

### The Problem

**schema.py** does not have a `duration_hours` field, but **mpp_reader.py** (_read_xml, line 129) returns it:

```python
# In _read_xml() function
for task_elem in findall(root, "Tasks/Task"):
    hours = pt_to_hours(get_text(task_elem, "Duration"))
    task_data = {
        "uid": get_int(task_elem, "UID"),
        "id": get_int(task_elem, "ID"),
        "name": get_text(task_elem, "Name"),
        "wbs": get_text(task_elem, "WBS"),
        "outline_level": get_int(task_elem, "OutlineLevel"),
        "start": get_text(task_elem, "Start"),
        "finish": get_text(task_elem, "Finish"),
        "duration": get_text(task_elem, "Duration"),
        "duration_hours": hours,  # ← NOT IN schema.py
        "percent_complete": get_float(task_elem, "PercentComplete"),
        # ... other fields ...
    }
    data["tasks"].append(task_data)
```

### Fix

Add to schema.py Task dataclass (after `duration` field):

```python
duration_hours: Optional[float] = None
```

---

## Issue #3: Source Tracking Fields Never Populated

### The Problem

**schema.py** defines source tracking fields (lines 33-34):

```python
@dataclass
class Task:
    # ...
    planned_pct_source: Literal["mpp", "computed", ""] = ""
    gap_pct_source: Literal["mpp", "computed", ""] = ""
```

**But mpp_reader.py** never populates them. Both _read_mpp and _read_xml initialize them but never set the source:

```python
# From _read_mpp (line 71-72):
"planned_pct": float(str(t.getNumber(4) or 0)) if t.getNumber(4) else None,
"gap_pct": float(str(t.getNumber(3) or 0)) if t.getNumber(3) else None,
# ↑ These are returned but sources not tracked

# From _read_xml (line 138-139):
"planned_pct": None,
"gap_pct": None,
# ↑ Always None in XML, and again no source tracking
```

**gap.md** (lines 36-37) explicitly requires this:

```markdown
Output always includes `"source": "mpp"` or `"source": "computed"` per field.

**Why this matters**: Project managers in XLSmart embed pre-reviewed Plan% and Gap% 
values in custom fields. Computing from schedule data can diverge by up to 40 
percentage points from the PM-approved values...
```

### Fix

Modify mpp_reader.py to track sources. In _read_mpp (after line 72):

```python
# BEFORE (lines 71-72):
"planned_pct": float(str(t.getNumber(4) or 0)) if t.getNumber(4) else None,
"gap_pct": float(str(t.getNumber(3) or 0)) if t.getNumber(3) else None,

# AFTER (should be):
"planned_pct": float(str(t.getNumber(4) or 0)) if t.getNumber(4) else None,
"planned_pct_source": "mpp" if t.getNumber(4) else "",
"gap_pct": float(str(t.getNumber(3) or 0)) if t.getNumber(3) else None,
"gap_pct_source": "mpp" if t.getNumber(3) else "",
```

Similarly in _read_xml (after line 139):

```python
# BEFORE (lines 138-139):
"planned_pct": None,
"gap_pct": None,

# AFTER (should be):
"planned_pct": None,
"planned_pct_source": "",
"gap_pct": None,
"gap_pct_source": "",
```

---

## Issue #4: SKILL.md Incomplete — Missing --resources and --wbs

### The Problem

**SKILL.md** (lines 42-50) documents READ command examples:

```bash
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp                    # full summary
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --json             # structured JSON
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --tasks            # task table
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --milestones       # milestones only
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --critical-path
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --overdue
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --summary-level 2  # WBS depth limit
```

**But mpp_reader.py** (lines 333-341) implements MORE flags:

```python
parser.add_argument("file", help="Input file path (.mpp or .xml)")
parser.add_argument("--json", action="store_true", help="Output as JSON")
parser.add_argument("--tasks", action="store_true", help="Show tasks table")
parser.add_argument("--milestones", action="store_true", help="Show milestones only")
parser.add_argument("--critical-path", action="store_true", help="Show critical path tasks")
parser.add_argument("--resources", action="store_true", help="Show resource list")      # ← NOT in SKILL.md
parser.add_argument("--wbs", action="store_true", help="Show WBS tree view")            # ← NOT in SKILL.md
parser.add_argument("--overdue", action="store_true", help="Show overdue tasks")
parser.add_argument("--summary-level", type=int, default=None,
```

### Fix

Add to SKILL.md READ section (after line 48):

```bash
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --resources        # resource list
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --wbs              # WBS tree view
```

---

## Issue #5: SKILL.md Incomplete — Missing --analyze for EXPORT

### The Problem

**SKILL.md** (lines 99-100) only shows 3 sheet options:

```bash
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --sheets overview,overdue
```

**But mpp_to_excel.py** (lines 504-508) has an additional `--analyze` flag:

```python
parser.add_argument("file", help="Input file (.mpp or .xml)")
parser.add_argument("--output", "-o", help="Output .xlsx path (default: auto-named)")
parser.add_argument("--sheets", default="all",
                    help="Comma-separated sheet names (default: all)")
parser.add_argument("--analyze", action="store_true",
                    help="Include Issues sheet with 5+ additional diagnostics")  # ← NOT in SKILL.md
```

And the script docstring (lines 2-17) explains this:

```python
"""Convert MPP/MSPDI files to Excel review spreadsheets.

Usage:
    python3 mpp_to_excel.py <file.mpp|file.xml> --output review.xlsx
    python3 mpp_to_excel.py <file.mpp|file.xml>                        # auto-names output
    python3 mpp_to_excel.py <file.mpp|file.xml> --analyze              # ← HERE in docstring!
    python3 mpp_to_excel.py <file.mpp|file.xml> --sheets overview,overdue  # selected sheets

Generates a 5-sheet Excel workbook (6 with --analyze):
  - Overview: project info, workstream progress (Level 1 + Level 2 phases)
  - All Tasks: full task list with color coding (red=overdue, yellow=summary, green=done)
  - Overdue: overdue leaf tasks with days-overdue calculation
  - Workstreams: summary tasks at Level 1-3 with % complete
  - Gantt: week-level bar chart for L1+L2 tasks with progress colors and today line
  - Issues (--analyze only): all diagnostics in one filterable table  ← HERE!
```

### Fix

Add to SKILL.md EXPORT section (after line 100):

```bash
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --analyze        # with issues analysis
```

---

## Issue #6: SKILL.md Incomplete — Missing EDIT fields

### The Problem

**SKILL.md** (lines 134-152) shows these EDIT examples:

```bash
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --percent-complete 90

python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --name "Web App" --finish "2026-04-20T17:00:00"
```

**But mspdi_editor.py** (lines 314-336) supports MORE fields:

```python
# Update operation flags
op_group.add_argument("--update-task", action="store_true", help="Update a task")
op_group.add_argument("--delete-task", action="store_true", help="Delete a task")
op_group.add_argument("--add-task", action="store_true", help="Add a new task")
op_group.add_argument("--batch-update", metavar="JSON_FILE", help="Batch update from JSON")

# Task fields for update/add
parser.add_argument("--uid", type=int, help="Task UID")
parser.add_argument("--name", help="Task name")
# ... existing fields ...
parser.add_argument("--start", help="Start date (YYYY-MM-DDTHH:MM:SS)")
parser.add_argument("--finish", help="Finish date")
parser.add_argument("--actual-start", help="Actual start date")        # ← NOT in SKILL.md
parser.add_argument("--actual-finish", help="Actual finish date")      # ← NOT in SKILL.md
parser.add_argument("--duration-days", type=float, help="Duration in working days")
parser.add_argument("--notes", help="Task notes")
parser.add_argument("--task-name", help="New task name (for update)")   # ← Confusing!
parser.add_argument("--milestone", action="store_true", help="Mark as milestone")
# ... more fields for add-task ...
parser.add_argument("--outline-level", type=int, help="Outline level for new task")
parser.add_argument("--after-uid", type=int, help="Insert after this UID")
```

### Fix

Add to SKILL.md EDIT section (after line 139):

```bash
# Update actual dates
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --actual-start "2026-04-15T08:00:00" --actual-finish "2026-04-20T17:00:00"

# Set milestone flag
python3 SKILL_DIR/scripts/mspdi_editor.py input.xml --output out.xml \
    --update-task --uid 5 --milestone
```

---

## Issue #7: GAP Analysis Default Behavior Undocumented

### The Problem

**SKILL.md** (line 59) claims:

```markdown
# Single file, current date
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp
```

**But mpp_plan_vs_actual.py** (lines 454-459) requires at least one date option:

```python
parser.add_argument("files", nargs="+", help="One or more MPP or XML files")
parser.add_argument("--date", help="Single cutoff date YYYY-MM-DD")
parser.add_argument("--dates", help="Comma-separated cutoff dates YYYY-MM-DD")
parser.add_argument("--weeks", type=int, help="Generate N weekly cutoff dates (Fridays)")
parser.add_argument("--json", action="store_true", help="Output JSON")
parser.add_argument("--excel", help="Output Excel file path")
```

The code doesn't show what happens when none of `--date`, `--dates`, or `--weeks` is provided. SKILL.md implies it defaults to "current date", but this needs verification in the actual main() function.

### Fix

Need to verify behavior: either document the default in SKILL.md or update code to handle the default case properly.

---

## Issue #8: Confusing --task-name vs --name in mspdi_editor.py

### The Problem

**mspdi_editor.py** (lines 321 and 331) has BOTH:

```python
parser.add_argument("--name", help="Task name")
# ... later ...
parser.add_argument("--task-name", help="New task name (for update)")
```

It's unclear:
- When to use `--name` vs `--task-name`?
- Are they aliases?
- Is one deprecated?

Looking at the code (lines 75-96), the `_update_task_fields()` function maps:

```python
field_map = {
    "name": "Name",
    # ...
}

for key, value in updates.items():
    if key in field_map:
        set_text(task_elem, field_map[key], str(value))
    # ...
```

So it looks like `--name` and `--task-name` might both work, or one overrides the other. This needs clarification.

### Fix

Document in SKILL.md EDIT section which one to use, or consolidate to a single flag in the code.

---

## Summary of Code References

| Issue | File | Lines | Type |
|-------|------|-------|------|
| Missing `critical` field | schema.py | 18-50 | Missing definition |
| Missing `duration_hours` | schema.py | 18-50 | Missing definition |
| Untracked sources | mpp_reader.py | 71-72, 138-139 | Missing logic |
| Missing `--resources` | SKILL.md | 42-50 | Incomplete doc |
| Missing `--wbs` | SKILL.md | 42-50 | Incomplete doc |
| Missing `--analyze` | SKILL.md | 99-100 | Incomplete doc |
| Missing `--actual-*` | SKILL.md | 134-152 | Incomplete doc |
| Confusing `--task-name` | mspdi_editor.py | 321, 331 | Unclear API |
| Default behavior | SKILL.md | 59 | Misleading doc |

