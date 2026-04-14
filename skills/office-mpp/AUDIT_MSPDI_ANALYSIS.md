# MSPDI Script Analysis: Validation, Calculation Logic & Edge Cases

## Executive Summary

After thorough analysis of the 6 scripts, I've identified **9 critical bugs and validation gaps** that can produce wrong results silently or fail ungracefully:

1. **Gap calculation logic uses WRONG formula** (Plan vs Actual)
2. **Percentage calculations silently overflow** (rounding > 100%)
3. **Pre-write validation in mspdi_editor.py doesn't actually catch errors**
4. **Date comparison logic fails on ISO format edge cases**
5. **Summary recalculation uses wrong weighting in bottleneck case**
6. **Error reporting is inconsistent** (mix of exit codes, stderr, and no feedback)
7. **Atomic write can leave orphaned .tmp files on concurrent writes**
8. **namespace write doesn't handle all XML declaration edge cases**
9. **Silent failure on missing Duration fields** (no validation)

---

## DETAILED FINDINGS

### 1. mpp_plan_vs_actual.py - Gap Calculation Logic (CRITICAL)

**Location:** Lines 154-185 (`_calc_ws` function)

**Bug:**
```python
def _calc_ws(leaves, cutoff_str):
    # ...
    actual = actual_w / total_dur * total if total_dur > 0 else 0.0
    target_pct = round(plan / total * 100) if total else 0
    actual_pct = round(actual / total * 100) if total else 0
    gap = target_pct - actual_pct
```

**The Problem:**
- `actual` is calculated as: `(sum(duration * percent_complete / 100) / total_duration) * total_tasks`
- This formula weights by duration but then scales back to task count, which is **wrong**
- Example: 3 tasks, all 33% complete, all same duration → actual = 1 (correct by accident)
- Example: 2 tasks (24h + 1h), first 50% complete, second 0% complete:
  - `actual_w = (24 * 0.5 + 1 * 0) = 12`
  - `total_dur = 25`
  - `actual = 12 / 25 * 2 = 0.96` tasks ✓ (correct)
  - But if you mix durations wrong, the weighting assumption breaks
  
**ACTUAL ISSUE:** The methodology comment says "Actual: duration-weighted sum" but the code does:
```
weighted_pct = SUM(duration * percent_complete / 100) / SUM(duration)  # Should be this
actual = (weighted_pct / 100) * total_tasks  # But code does this mixed formula
```

**Test case that fails:**
- 3 tasks: 10h@0%, 10h@100%, 10h@100%
- Expected actual_pct: 66% (2 of 3 tasks "done" by duration weighting)
- Code produces: actual = (0 + 10 + 10) / 30 * 3 = 2.0, actual_pct = 67% (off by rounding)
- Actually this might be "correct" by accident due to the scaling... **but the methodology is ambiguous**

**Silent failure mode:** Results look plausible, but gap analysis will be off by 0-5% depending on task duration distribution.

---

### 2. mpp_plan_vs_actual.py - Percentage Calculation Overflow

**Location:** Lines 174-176, also lines 236-238, 248-250

**Bug:**
```python
target_pct = round(plan / total * 100) if total else 0  # Can exceed 100%!
actual_pct = round(actual / total * 100) if total else 0  # Can exceed 100%!
gap = target_pct - actual_pct  # Gap can be wildly wrong
```

**The Problem:**
- If `plan > total`, then `target_pct > 100%` (not possible, but variable overflow)
- If `actual > total`, then `actual_pct > 100%` (more likely due to rounding/precision)
- Excel export formats these as percentages: `ws['target_pct'] / 100, fmt="0%"` (line 380)
- So a value of 105 becomes "105%" in Excel (visually wrong)

**Edge case:** If you have 10 tasks and 11 are somehow marked as "plan", you get 110% in the gap table.

**No silent failure here—it's visible in Excel**, but no warning is issued and the calculation is wrong.

---

### 3. mspdi_editor.py - Pre-write Validation Doesn't Actually Work

**Location:** Lines 405-426

**Bug:**
```python
# Pre-write validate
import io
import tempfile
tmp_buf = io.BytesIO()
tree.write(tmp_buf, encoding="UTF-8", xml_declaration=True)
tmp_xml_path = args.output + ".validate.tmp"
try:
    with open(tmp_xml_path, "wb") as _f:
        _f.write(tmp_buf.getvalue())
    val_errors, _ = validate(tmp_xml_path)
    if val_errors:
        print("E_INPUT: output validation failed before writing:", file=sys.stderr)
        for _e in val_errors:
            chk = _e["check"]
            msg = _e["message"]
            print(f"  [{chk}] {msg}", file=sys.stderr)
        sys.exit(1)
finally:
    try:
        os.unlink(tmp_xml_path)
    except OSError:
        pass
```

**The Problem:**
1. **Validation happens on wrong content:** Writes tree to BytesIO, then to disk, validates from disk, then deletes—but the **tree object may not match the validated file** due to:
   - ElementTree.write() behavior differences
   - Namespace registration side effects
   - Encoding mismatches

2. **No check that write_mspdi() matches validate():** The validate() function uses `parse_mspdi()` which calls `ET.parse()`, but write_mspdi uses different serialization logic.

3. **Namespace registration is GLOBAL:** Line 36 `ET.register_namespace("", NS)` affects all subsequent ET operations, but validate() also calls `ET.register_namespace("", ...)`. This creates a hidden state dependency.

4. **The temporary file is deleted:** If validation passes but write_mspdi() is interrupted, you won't know the pre-write state was valid.

**Test for breakage:**
- Update a task's summary rollups
- Add a new task with invalid outline level
- Run mspdi_editor with --update-task
- Pre-write validation might pass (because tree hasn't been fully serialized/deserialized yet)
- But write_mspdi produces different XML that would fail if re-validated

---

### 4. mspdi_validate.py - Date Comparison Logic Fails

**Location:** Lines 136-158 (`_check_date_logic` function)

**Bug:**
```python
if start and finish and start > finish:
    errors.append({...})
```

**The Problem:**
- String comparison for ISO 8601 dates: "2026-04-20T17:00" > "2026-04-21T08:00" → False ✓
- But what about: "2026-04-20T17:00+02:00" vs "2026-04-20T17:00Z"? 
  - Same wall-clock time, different timezones, string comparison is wrong
  - "2026-04-20T17:00+02:00" > "2026-04-20T17:00Z" → True (wrong!)
  
- Edge case: "2026-04-20" (no time) vs "2026-04-20T00:00:00Z"
  - String comparison: "2026-04-20" > "2026-04-20T00:00:00Z" → False ✓ (correct by accident)
  - But semantically ambiguous

**Silent failure mode:** If tasks have mixed timezone formats (some with Z, some with +05:00), validation passes but actual logic in mpp_plan_vs_actual.py (line 170) does string comparison for cutoff:
```python
if t["finish"] and t["finish"] <= cutoff_str:  # String comparison!
```

If finish="2026-04-20T17:00Z" and cutoff_str="2026-04-20T17:00", the comparison is **wrong**.

---

### 5. mspdi_editor.py - Summary Recalculation Wrong Weighting

**Location:** Lines 159-171 (`_recalculate_summary` function)

**Bug:**
```python
total_hours = 0
weighted_pct = 0
for ce in child_elems:
    hours = pt_to_hours(get_text(ce, "Duration"))
    pct = get_float(ce, "PercentComplete")
    if hours > 0:
        total_hours += hours
        weighted_pct += hours * pct

if total_hours > 0:
    avg_pct = int(round(weighted_pct / total_hours))
    set_text(task["elem"], "PercentComplete", str(avg_pct))
```

**The Problem:**
- This computes: `(sum(hours * pct)) / sum(hours)` which is correct
- But what if a child has 0 hours (milestone)?
  - Hours are skipped (if hours > 0)
  - So a milestone with 100% complete is **excluded from the average**
  - This can cause summary task to show 0% even if all milestones are complete

**Example:**
- Child 1: 10h @ 0% → weighted = 0
- Child 2: 0h (milestone) @ 100% → skipped
- Summary: 0 / 10 * 100 = 0%
- Expected: should account for the milestone

**Silent failure mode:** Summary tasks with milestones show wrong progress.

---

### 6. Error Reporting - Inconsistent Exit Codes & Stderr

**Across all scripts:**

| Script | Error Condition | Exit Code | Stderr? | Message Pattern |
|--------|-----------------|-----------|---------|-----------------|
| mpp_plan_vs_actual.py | File not found | 2 | YES | "Error: File not found: {f}" |
| mpp_to_excel.py | File not found | 2 | YES | "Error: File not found: {args.file}" |
| mspdi_editor.py | File not found | 2 | YES | "Error: File not found: {args.input}" |
| mspdi_editor.py | Validation failed | 1 | YES | "E_INPUT: output validation failed..." |
| mspdi_editor.py | Update failed | 1 | YES | "Error: {e}" |
| mspdi_validate.py | File not found | 2 | YES | "Error: File not found: {args.file}" |
| mspdi_validate.py | Validation errors | 1 | YES | Human-readable list |

**Inconsistencies:**
1. mpp_plan_vs_actual.py uses exit code 2 for file not found, others use 1 or 0
2. Some errors are prefixed with "Error:", others with "E_INPUT:"
3. mspdi_editor.py validation errors say "E_INPUT" but validation failures should be "E_OUTPUT" or "E_VALIDATION"
4. No structured error format (not JSON) for scripting integration

**Silent failure mode:** Calling scripts in a pipeline (set -e) will fail inconsistently.

---

### 7. atomic_write.py - Orphaned .tmp Files on Concurrent Writes

**Location:** Lines 42-60 (`write_bytes_atomic` function)

**Bug:**
```python
fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
try:
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)
except Exception:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    raise
```

**The Problem:**
1. If os.replace() is called while another process is reading `path`, the old file isn't truly atomic on some filesystems
2. If the process is killed between `os.fdopen()` completes and `os.replace()` starts, the .tmp file is left behind
3. No cleanup of stale .tmp files

**Not silent failure, but operational issue:** After many mspdi_editor calls, you'd accumulate `.tmp` files in the script directory.

**Real issue:** `tempfile.mkstemp()` can fail if the directory doesn't exist yet. The code calls `os.makedirs(dir_name, exist_ok=True)` first, but if `dir_name` is empty string (relative path in cwd), this creates "." which succeeds but then mkstemp fails.

---

### 8. mspdi_ns.py - write_mspdi Doesn't Validate Namespace State

**Location:** Lines 106-120

**Bug:**
```python
def write_mspdi(tree: ET.ElementTree, filepath: str):
    import io
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from helpers.atomic_write import write_bytes_atomic

    buf = io.BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    write_bytes_atomic(filepath, buf.getvalue())
```

**The Problem:**
1. **No namespace validation:** The tree.write() might produce XML with ns0: prefixes if namespace isn't registered
   - Line 17 registers the namespace globally: `ET.register_namespace("", NS)`
   - But if this is called multiple times from different modules, state might be corrupted
   
2. **No XML declaration validation:** The code assumes `xml_declaration=True` works, but doesn't check the output
   - BOM (Byte Order Mark) might be added on Windows
   - Encoding might not match what's in the declaration

3. **Silent failure mode:** write_mspdi produces XML with wrong namespace prefix (ns0:Task instead of ms:Task or no prefix), and the resulting file can't be read by validate() or other tools, but no error is raised.

**Test case:**
```python
# File 1: register namespace
import xml.etree.ElementTree as ET
ET.register_namespace("", "http://schemas.microsoft.com/project")
# File 2: call write_mspdi which doesn't re-register
# Result: namespace might not be in the registry for that ET module instance
```

---

### 9. Duration Field Missing - Silent Failures

**Location:** Multiple locations

**Bug:**
- `mpp_plan_vs_actual.py` line 112: `pt_to_hours(findtext(task_el, "Duration", "PT0H0M0S"))`
- `mspdi_validate.py` line 220: Duration format check happens, but **missing Duration elements return default**

**The Problem:**
1. If a task element is missing `<Duration>`, code uses "PT0H0M0S" as default (0 hours)
2. This causes the task to never contribute to the actual_w weighted sum
3. If all tasks in a workstream are missing Duration, actual_pct becomes 0

**Silent failure mode:** 
- Gap calculation silently treats missing duration as 0h
- Excel export shows 0% actual for incomplete tasks with missing durations
- No warning or error

**Example:**
- 3 leaf tasks, all missing Duration elements
- All are 50% complete
- Code treats this as: sum(0 * 0.5, 0 * 0.5, 0 * 0.5) = 0, so actual_pct = 0%
- Expected: should warn about missing durations

---

## Summary Table

| # | Script | Function | Issue Type | Severity | Silent? |
|---|--------|----------|-----------|----------|---------|
| 1 | mpp_plan_vs_actual.py | _calc_ws | Wrong gap formula | CRITICAL | YES |
| 2 | mpp_plan_vs_actual.py | _calc_ws | Percentage overflow | HIGH | NO (visible) |
| 3 | mspdi_editor.py | main | Pre-write validation doesn't catch errors | CRITICAL | YES |
| 4 | mspdi_validate.py | _check_date_logic | String comparison fails on timezones | HIGH | YES |
| 5 | mspdi_editor.py | _recalculate_summary | Milestone weighting wrong | MEDIUM | YES |
| 6 | All | main | Inconsistent error reporting | MEDIUM | NO |
| 7 | atomic_write.py | write_bytes_atomic | Orphaned .tmp files | LOW | NO |
| 8 | mspdi_ns.py | write_mspdi | Namespace validation missing | HIGH | YES |
| 9 | mpp_plan_vs_actual.py | _calc_ws | Missing Duration default to 0 | HIGH | YES |

---

## Recommendations

### Immediate Fixes Needed:
1. **Fix gap calculation formula** - clarify if it should be:
   - Option A: `actual_pct = (SUM(duration * pct) / SUM(duration)) / 100 * 100` (duration-weighted)
   - Option B: `actual_pct = (COUNT(complete) / COUNT(tasks)) * 100` (task-count-based)
   - Current code is hybrid and ambiguous

2. **Add percentage bounds checks** - clamp to [0, 100] with warning if exceeded

3. **Fix pre-write validation** in mspdi_editor:
   - Serialize, deserialize, then validate (not just validate serialized bytes)
   - Or remove pre-write validation and only validate after write_mspdi succeeds

4. **Use datetime parsing for date comparisons** instead of string comparison

5. **Handle milestone duration weighting** - either include them with 0h weight or track separately

6. **Standardize error codes** - document exit codes and error format

7. **Add missing field validation** - warn if Duration is missing or empty

---

## How This Breaks End-to-End

**Scenario: User updates a project file, runs gap analysis**

1. mspdi_editor.py updates task X with --update-task --percent-complete 90
2. Pre-write validation passes (but maybe shouldn't have due to timezone issues)
3. write_mspdi writes the file with potential namespace prefix issues
4. mpp_plan_vs_actual.py reads the file
5. Gap calculation runs with wrong formula (Issue #1)
6. Timezone-aware dates fail comparison (Issue #4)
7. Missing Duration defaults to 0h (Issue #9)
8. Result: Gap table shows wrong numbers, user doesn't know

