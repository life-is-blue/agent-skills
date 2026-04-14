# office-mpp Skill Audit Report

## Summary

This audit compares the claims and commands in SKILL.md against the actual implementation in scripts and tests error handling. **Overall result: Multiple discrepancies found.**

---

## 1. SKILL.md Command Claims vs Actual CLI Arguments

### ✅ READ (mpp_reader.py) — ALL CORRECT

SKILL.md claims:
```bash
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --json
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --tasks
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --milestones
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --critical-path
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --overdue
python3 SKILL_DIR/scripts/mpp_reader.py project.mpp --summary-level 2
```

**Actual implementation** (mpp_reader.py lines 333-341):
- ✅ `--json` (line 334)
- ✅ `--tasks` (line 335)
- ✅ `--milestones` (line 336)
- ✅ `--critical-path` (line 337) — matches SKILL.md
- ✅ `--resources` (line 338) — **NOT mentioned in SKILL.md but exists**
- ✅ `--wbs` (line 339) — **NOT mentioned in SKILL.md but exists**
- ✅ `--overdue` (line 340)
- ✅ `--summary-level` (line 341)

**Issue**: SKILL.md is incomplete. It documents READ but omits `--resources` and `--wbs` flags.

---

### ⚠️ GAP (mpp_plan_vs_actual.py) — DISCREPANCY FOUND

SKILL.md claims:
```bash
python3 SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3 --excel gap.xlsx
```

**Actual implementation** (mpp_plan_vs_actual.py lines 454-459):
```python
parser.add_argument("files", nargs="+", help="One or more MPP or XML files")
parser.add_argument("--date", help="Single cutoff date YYYY-MM-DD")        # ← NEW, not in SKILL.md
parser.add_argument("--dates", help="Comma-separated cutoff dates...")
parser.add_argument("--weeks", type=int, help="Generate N weekly cutoff dates (Fridays)")
parser.add_argument("--json", action="store_true", help="Output JSON")
parser.add_argument("--excel", help="Output Excel file path")
```

**Issue**: SKILL.md line 69 says `--dates 2026-04-18,2026-04-25` but also mentions `--date` option should exist (line 59: "Single file, current date" implies `--date` without arguments). However, **`--date` IS implemented** as a positional-less option on line 455. This should be documented.

---

### ✅ EXPORT (mpp_to_excel.py) — Mostly correct

SKILL.md claims:
```bash
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --output review.xlsx
python3 SKILL_DIR/scripts/mpp_to_excel.py project.mpp --sheets overview,overdue
```

**Actual implementation** (mpp_to_excel.py lines 504-508):
- ✅ `file` (positional, line 504)
- ✅ `--output` / `-o` (line 505)
- ✅ `--sheets` (line 506)
- ⚠️ `--analyze` (line 508) — **NOT mentioned in SKILL.md but exists**

**Issue**: `--analyze` flag missing from SKILL.md documentation.

---

### ⚠️ CREATE (mspdi_create.py) — Discrepancy on CLI args

SKILL.md claims:
```bash
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --title "My Project" --start 2026-04-15
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --from-json spec.json
python3 SKILL_DIR/scripts/mspdi_create.py --output plan.xml --from-template custom.xml --title "New"
```

**Actual implementation** (mspdi_create.py lines 228-232):
```python
parser.add_argument("--output", required=True, help="Output XML file path")
parser.add_argument("--title", default="New Project", help="Project title")
parser.add_argument("--start", default=None, help="Project start date (YYYY-MM-DD)")
parser.add_argument("--from-json", default=None, help="JSON file with project data")
parser.add_argument("--from-template", default=None, help="Custom MSPDI XML template")
```

**Status**: ✅ All documented options exist. No discrepancies.

---

### ⚠️ EDIT (mspdi_editor.py) — Multiple undocumented flags

SKILL.md claims these operations:
```bash
--update-task --uid 5 --percent-complete 90
--update-task --name "Web App" --finish "2026-04-20T17:00:00"
--batch-update updates.json
--delete-task --uid 5
--add-task --name "New Task" --outline-level 3 --after-uid 5 ...
```

**Actual implementation** (mspdi_editor.py lines 314-336):
```python
op_group.add_argument("--update-task", action="store_true")
op_group.add_argument("--delete-task", action="store_true")
op_group.add_argument("--add-task", action="store_true")
op_group.add_argument("--batch-update", metavar="JSON_FILE")

# Common
parser.add_argument("--uid", type=int)
parser.add_argument("--name")
parser.add_argument("--percent-complete", type=float)
parser.add_argument("--start")
parser.add_argument("--finish")
parser.add_argument("--actual-start")                  # ← NEW, not in SKILL.md
parser.add_argument("--actual-finish")                 # ← NEW, not in SKILL.md
parser.add_argument("--duration-days", type=float)
parser.add_argument("--notes")
parser.add_argument("--task-name")                     # ← Exists but confusing with --name
parser.add_argument("--milestone", action="store_true")
parser.add_argument("--outline-level", type=int)
parser.add_argument("--after-uid", type=int)
```

**Issues**:
1. `--actual-start` and `--actual-finish` are implemented but **not documented** in SKILL.md
2. `--task-name` exists but is **not mentioned** in SKILL.md

---

### ✅ VALIDATE (mspdi_validate.py) — Correct

SKILL.md claims:
```bash
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml --json
python3 SKILL_DIR/scripts/mspdi_validate.py file.xml --fix --output fixed.xml
```

**Actual implementation** (mspdi_validate.py lines 259-262):
- ✅ `file` (positional)
- ✅ `--json`
- ✅ `--fix`
- ✅ `--output`

**Status**: ✅ Correct. All documented options exist.

---

### ⚠️ Maintenance Scripts — Partially documented

SKILL.md mentions (line 201):
> Maintenance Scripts — REPORT, DIFF, CONVERT, and ANALYZE scripts are not primary Skill operations. Usage guides are in `references/maintenance.md`.

**Actual implementations checked**:
- ✅ `mpp_report.py` — 3 options: `--status`, `--todo`, `--json` (not in SKILL.md detail)
- ✅ `mpp_diff.py` — 3 options: `--json`, `-o`, `--output`  (not in SKILL.md detail)
- ✅ `mpp_converter.py` — 4 options: `--output-dir`, `--json-summary`, `--classify` (not in SKILL.md detail)
- ⚠️ `mpp_analyze.py` — **NOT documented even in SKILL.md utility section line 217**

**Issue**: `mpp_analyze.py` is referenced in SKILL.md line 217 but no usage example given. The argparse check didn't find it in our output (likely incomplete).

---

## 2. env_check.sh JSON Output Validation

**Test**: Running `bash scripts/env_check.sh --json`

**Result**: ✅ Valid JSON output

```json
{"ok": true, "missing": [], "fix_commands": []}
```

- ✅ JSON is well-formed and parseable by `python3 -m json.tool`
- ✅ Output format matches SKILL.md (line 192) specification: `{"ok": bool, "missing": [], "fix_commands": []}`
- ✅ Exit code is 0 (success) when all deps present
- ✅ Tested with --json flag — works correctly

**Additional check on error cases**: The script correctly constructs JSON arrays even when dependencies are missing (from code inspection of lines 128-144). Arrays are properly escaped.

---

## 3. Schema.py vs mpp_reader.py Output — CRITICAL DISCREPANCY

### Schema.py defines:

```python
@dataclass
class Task:
    uid: int                                           # REQUIRED
    id: int                                            # REQUIRED
    name: str                                          # REQUIRED
    start: str = ""
    finish: str = ""
    duration: str = ""
    percent_complete: float = 0.0
    outline_level: int = 0
    summary: bool = False
    milestone: bool = False
    planned_pct: Optional[float] = None
    gap_pct: Optional[float] = None
    planned_pct_source: Literal["mpp", "computed", ""] = ""
    gap_pct_source: Literal["mpp", "computed", ""] = ""
    baseline_start: str = ""
    baseline_finish: str = ""
    baseline_duration: str = ""
    finish_variance: str = ""
    predecessors: str = ""
    resource_names: str = ""
    notes: str = ""
    wbs: str = ""
    calendar_uid: Optional[int] = None
    number3: Optional[float] = None
    number4: Optional[float] = None
```

### mpp_reader.py actually returns:

```python
# From _read_mpp (line 54-73):
task_data = {
    "uid": ...,
    "id": ...,
    "name": ...,
    "wbs": ...,
    "outline_level": ...,
    "start": ...,
    "finish": ...,
    "duration": ...,
    "percent_complete": ...,
    "summary": ...,
    "milestone": ...,
    "critical": ...,                                  # ← NOT in schema.py!
    "notes": ...,
    "baseline_start": ...,
    "baseline_finish": ...,
    "finish_variance": ...,
    "planned_pct": ...,
    "gap_pct": ...,
}

# From _read_xml (line 120-140):
task_data = {
    "uid": ...,
    "id": ...,
    "name": ...,
    "wbs": ...,
    "outline_level": ...,
    "start": ...,
    "finish": ...,
    "duration": ...,
    "duration_hours": ...,                           # ← NOT in schema.py!
    "percent_complete": ...,
    "summary": ...,
    "milestone": ...,
    "critical": ...,                                 # ← NOT in schema.py!
    "notes": ...,
    "baseline_start": ...,
    "baseline_finish": ...,
    "finish_variance": ...,
    "planned_pct": None,                             # Always None in XML reader
    "gap_pct": None,                                 # Always None in XML reader
}
```

### CRITICAL ISSUES:

1. **`critical` field**: Present in mpp_reader output (both MPP and XML) but **NOT in schema.py Task dataclass**
   - MPP reader: line 66 returns `"critical"`
   - XML reader: line 133 returns `"critical"`
   - Schema.py: **Missing**

2. **`duration_hours` field**: Returned by XML reader but **NOT in schema.py**
   - XML reader: line 129 returns `"duration_hours"`
   - Schema.py: **Missing**

3. **Gap% calculation fields missing**: Schema defines `number3` and `number4` but mpp_reader uses `gap_pct` and `planned_pct` names instead
   - Schema names: `number3`, `number4` (following MS Project convention)
   - Reader names: `gap_pct`, `planned_pct` (descriptive names)
   - These should map but are differently named

4. **Source tracking fields underfilled**: Schema defines `planned_pct_source` and `gap_pct_source` but mpp_reader **never populates them**
   - mpp_reader sets them to None / empty string
   - gap.md (line 36-37) states output should include `"source": "mpp"` or `"source": "computed"`
   - But mpp_reader doesn't do this!

---

## 4. SKILL.md Command Accuracy Summary

### Missing/Undocumented Flags:

| Script | Flag | Status | Doc Location |
|--------|------|--------|---|
| mpp_reader.py | `--resources` | Implemented, not documented | Line 42-50 |
| mpp_reader.py | `--wbs` | Implemented, not documented | Line 42-50 |
| mpp_to_excel.py | `--analyze` | Implemented, not documented | Line 99-100 |
| mspdi_editor.py | `--actual-start` | Implemented, not documented | Line 134-139 |
| mspdi_editor.py | `--actual-finish` | Implemented, not documented | Line 134-139 |
| mspdi_editor.py | `--task-name` | Implemented, unclear purpose | Line 138-139 |
| mpp_plan_vs_actual.py | `--date` | Implemented, implicit only | Line 59 |

### Misleading Commands:

| Script | Issue | Location |
|--------|-------|----------|
| mpp_plan_vs_actual.py | First example says "Single file, current date" but requires `--date` or `--dates` | Line 59 |
| mpp_plan_vs_actual.py | Documentation suggests `--date` is implicit when not provided | Line 59 |

---

## 5. Exit Codes and Error Handling — ✅ Correct

From SKILL.md lines 186-195:

| Code | Prefix | Status |
|------|--------|--------|
| 0 | — | ✅ Scripts follow this |
| 1 | `E_INPUT:` | ✅ Used in mspdi_validate.py, mspdi_editor.py |
| 2 | `E_ENV:` | ✅ Used in env_check.sh (line 39) |
| 2 | `E_IO:` | ✅ Implemented in scripts |

**Note**: Exit code `2` is used for both `E_ENV:` and `E_IO:` errors, which is correct per SKILL.md.

---

## 6. Key Invariants — Need Verification

From SKILL.md lines 176-183, checking against actual implementations:

### Invariant 1: "MSPDI XML is the editable format — MPP is binary read-only"
- ✅ **Verified**: mpp_reader reads both, but mspdi_editor only accepts XML (no `--mpp` support)

### Invariant 2: "UID uniqueness"
- ✅ **Verified**: mspdi_validate.py lines 91-107 enforce UID uniqueness check

### Invariant 3: "Summary rollup — Parent summary fields are computed from children"
- ⚠️ **Not verified in audit**: mspdi_editor and mspdi_create don't explicitly enforce this

### Invariant 4: "Namespace — Always `http://schemas.microsoft.com/project`"
- ✅ **Verified**: Used in mspdi_ns.py, registered in scripts via `ET.register_namespace("", NS)`

### Invariant 5: "Duration format — `PT###H##M##S`"
- ✅ **Verified**: duration_utils.py enforces this format in `is_valid_pt()` and `days_to_pt()`

---

## Recommendations

### High Priority:

1. **Update SKILL.md to document all available flags**:
   - Add `--resources` and `--wbs` to READ section (line 42-50)
   - Add `--analyze` to EXPORT section (line 96-100)
   - Add `--actual-start`, `--actual-finish` to EDIT section (line 134-152)
   - Clarify `--date` vs `--dates` in GAP section

2. **Fix schema.py to match mpp_reader output**:
   - Add `critical: bool = False` field to Task dataclass
   - Add `duration_hours: Optional[float] = None` field to Task dataclass
   - Clarify mapping between `gap_pct` ↔ `number3` and `planned_pct` ↔ `number4`
   - Populate `planned_pct_source` and `gap_pct_source` in mpp_reader (gap.md requirement)

3. **Clarify mpp_plan_vs_actual default behavior**:
   - Document what happens when neither `--date`, `--dates`, nor `--weeks` is provided
   - SKILL.md line 59 implies it defaults to "current date" but code doesn't show this

### Medium Priority:

4. **mspdi_editor.py clarification**:
   - `--task-name` appears to be a duplicate/alias of `--name`? Document the difference or consolidate.

5. **mpp_analyze.py**:
   - Still incomplete from grep output. Document in SKILL.md utility section or remove from line 217.

---

## Test Results Summary

| Component | Status | Notes |
|-----------|--------|-------|
| SKILL.md READ commands | ⚠️ Incomplete | Missing `--resources`, `--wbs` docs |
| SKILL.md GAP commands | ⚠️ Incomplete | Ambiguous default behavior |
| SKILL.md EXPORT commands | ⚠️ Incomplete | Missing `--analyze` docs |
| SKILL.md EDIT commands | ⚠️ Incomplete | Missing `--actual-*` field docs |
| SKILL.md VALIDATE commands | ✅ Accurate | All documented options match |
| env_check.sh --json | ✅ Valid JSON | Parseable, correct format |
| schema.py vs mpp_reader | ❌ MISMATCHED | Missing fields: `critical`, `duration_hours` |
| Exit codes | ✅ Correct | Match spec in SKILL.md |
| Duration format | ✅ Correct | PT###H##M##S enforced |
| Namespace handling | ✅ Correct | Proper registration |
| UID uniqueness | ✅ Verified | Enforced in validate |

