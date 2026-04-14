#!/usr/bin/env python3
"""Validate MSPDI XML structural integrity.

Usage:
    python3 mspdi_validate.py file.xml                     # full validation
    python3 mspdi_validate.py file.xml --json              # machine-readable results
    python3 mspdi_validate.py file.xml --fix --output f.xml # auto-fix common issues

Exit codes: 0=valid, 1=errors found, 2=file not found/parse error
"""

import sys
import os
import argparse
import json
import re

sys.path.insert(0, os.path.dirname(__file__))

from helpers.mspdi_ns import (
    parse_mspdi, findall, find, get_text, get_int, get_float, set_text,
    write_mspdi, tag
)
from helpers.duration_utils import is_valid_pt

import xml.etree.ElementTree as ET
ET.register_namespace("", "http://schemas.microsoft.com/project")


def validate(filepath):
    """Run all validation checks. Returns (errors, warnings) lists."""
    errors = []
    warnings = []

    try:
        tree = parse_mspdi(filepath)
    except ET.ParseError as e:
        return [{"check": "parse", "message": f"XML parse error: {e}"}], []
    except FileNotFoundError:
        return [{"check": "parse", "message": f"File not found: {filepath}"}], []

    root = tree.getroot()

    # 1. Structure check
    _check_structure(root, errors, warnings)

    # 2. UID uniqueness
    _check_uid_uniqueness(root, errors)

    # 3. WBS consistency
    _check_wbs_consistency(root, errors, warnings)

    # 4. Date logic
    _check_date_logic(root, errors, warnings)

    # 5. Percentage range
    _check_percentage_range(root, errors)

    # 6. Assignment integrity
    _check_assignment_integrity(root, errors)

    # 7. Calendar reference
    _check_calendar_refs(root, errors, warnings)

    # 8. Duration format
    _check_duration_format(root, errors)

    return errors, warnings


def _check_structure(root, errors, warnings):
    """Check required sections exist."""
    required = ["Calendars", "Tasks"]
    optional = ["Resources", "Assignments"]

    for section in required:
        if find(root, section) is None:
            errors.append({
                "check": "structure",
                "message": f"Required section <{section}> is missing",
            })

    for section in optional:
        if find(root, section) is None:
            warnings.append({
                "check": "structure",
                "message": f"Optional section <{section}> is missing",
            })


def _check_uid_uniqueness(root, errors):
    """Check for duplicate UIDs in Tasks, Resources, Assignments."""
    for section_name, tag_name in [
        ("Tasks", "Task"),
        ("Resources", "Resource"),
        ("Assignments", "Assignment"),
    ]:
        uids = {}
        for elem in findall(root, f"{section_name}/{tag_name}"):
            uid = get_int(elem, "UID")
            name = get_text(elem, "Name", f"(UID={uid})")
            if uid in uids:
                errors.append({
                    "check": "uid_uniqueness",
                    "section": section_name,
                    "message": f"Duplicate {tag_name} UID={uid}: '{name}' and '{uids[uid]}'",
                })
            uids[uid] = name


def _check_wbs_consistency(root, errors, warnings):
    """Check WBS depth matches OutlineLevel, summary tasks have children."""
    tasks = findall(root, "Tasks/Task")
    task_list = [(get_int(t, "UID"), get_int(t, "OutlineLevel"),
                  get_int(t, "Summary") == 1, get_text(t, "Name")) for t in tasks]

    for i, (uid, ol, is_summary, name) in enumerate(task_list):
        if is_summary:
            # Check that next task has deeper level
            has_child = False
            for j in range(i + 1, len(task_list)):
                next_ol = task_list[j][1]
                if next_ol <= ol:
                    break
                if next_ol == ol + 1:
                    has_child = True
                    break
            if not has_child:
                warnings.append({
                    "check": "wbs_consistency",
                    "uid": uid,
                    "message": f"Summary task UID={uid} '{name}' has no children",
                })


def _check_date_logic(root, errors, warnings):
    """Check Start <= Finish, ActualStart <= ActualFinish."""
    for task_elem in findall(root, "Tasks/Task"):
        uid = get_int(task_elem, "UID")
        name = get_text(task_elem, "Name")
        start = get_text(task_elem, "Start")
        finish = get_text(task_elem, "Finish")
        actual_start = get_text(task_elem, "ActualStart")
        actual_finish = get_text(task_elem, "ActualFinish")

        if start and finish and start > finish:
            errors.append({
                "check": "date_logic",
                "uid": uid,
                "message": f"Task UID={uid} '{name}': Start ({start}) > Finish ({finish})",
            })

        if actual_start and actual_finish and actual_start > actual_finish:
            errors.append({
                "check": "date_logic",
                "uid": uid,
                "message": f"Task UID={uid} '{name}': ActualStart ({actual_start}) > ActualFinish ({actual_finish})",
            })


def _check_percentage_range(root, errors):
    """Check PercentComplete is in 0..100."""
    for task_elem in findall(root, "Tasks/Task"):
        uid = get_int(task_elem, "UID")
        name = get_text(task_elem, "Name")
        pct = get_float(task_elem, "PercentComplete")
        if pct < 0 or pct > 100:
            errors.append({
                "check": "percentage_range",
                "uid": uid,
                "message": f"Task UID={uid} '{name}': PercentComplete={pct} out of range [0,100]",
            })


def _check_assignment_integrity(root, errors):
    """Check that all Assignment TaskUID/ResourceUID reference existing entities."""
    task_uids = set()
    for t in findall(root, "Tasks/Task"):
        task_uids.add(get_int(t, "UID"))

    resource_uids = set()
    for r in findall(root, "Resources/Resource"):
        resource_uids.add(get_int(r, "UID"))

    for assn in findall(root, "Assignments/Assignment"):
        assn_uid = get_int(assn, "UID")
        task_uid = get_int(assn, "TaskUID")
        res_uid = get_int(assn, "ResourceUID")

        if task_uid not in task_uids:
            errors.append({
                "check": "assignment_integrity",
                "assignment_uid": assn_uid,
                "message": f"Assignment UID={assn_uid}: TaskUID={task_uid} does not exist",
            })
        # ResourceUID -65535 is the "unassigned" sentinel in MS Project
        if res_uid != -65535 and resource_uids and res_uid not in resource_uids:
            errors.append({
                "check": "assignment_integrity",
                "assignment_uid": assn_uid,
                "message": f"Assignment UID={assn_uid}: ResourceUID={res_uid} does not exist",
            })


def _check_calendar_refs(root, errors, warnings):
    """Check CalendarUID references exist in Calendars section."""
    cal_uids = set()
    for cal in findall(root, "Calendars/Calendar"):
        cal_uids.add(get_int(cal, "UID"))

    # Check project-level CalendarUID
    proj_cal = get_text(root, "CalendarUID")
    if proj_cal and int(proj_cal) not in cal_uids:
        warnings.append({
            "check": "calendar_ref",
            "message": f"Project CalendarUID={proj_cal} not found in Calendars section",
        })


def _check_duration_format(root, errors):
    """Check all duration strings match PT pattern."""
    for task_elem in findall(root, "Tasks/Task"):
        uid = get_int(task_elem, "UID")
        name = get_text(task_elem, "Name")
        duration = get_text(task_elem, "Duration")
        if duration and not is_valid_pt(duration):
            errors.append({
                "check": "duration_format",
                "uid": uid,
                "message": f"Task UID={uid} '{name}': Invalid duration format '{duration}'",
            })


def fix_common_issues(filepath, output_path):
    """Auto-fix common MSPDI issues. Returns (tree, fixes_applied)."""
    tree = parse_mspdi(filepath)
    root = tree.getroot()
    fixes = []

    # Fix percentage out of range
    for task_elem in findall(root, "Tasks/Task"):
        uid = get_int(task_elem, "UID")
        pct = get_float(task_elem, "PercentComplete")
        if pct < 0:
            set_text(task_elem, "PercentComplete", "0")
            fixes.append(f"UID={uid}: PercentComplete {pct} -> 0")
        elif pct > 100:
            set_text(task_elem, "PercentComplete", "100")
            fixes.append(f"UID={uid}: PercentComplete {pct} -> 100")

    write_mspdi(tree, output_path)
    return tree, fixes


def main():
    parser = argparse.ArgumentParser(
        description="Validate MSPDI XML structural integrity"
    )
    parser.add_argument("file", help="Input MSPDI XML file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Auto-fix common issues")
    parser.add_argument("--output", help="Output file for --fix")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    if args.fix:
        if not args.output:
            print("Error: --output required with --fix", file=sys.stderr)
            sys.exit(2)
        tree, fixes = fix_common_issues(args.file, args.output)
        if fixes:
            print(f"Applied {len(fixes)} fix(es):")
            for f in fixes:
                print(f"  - {f}")
        else:
            print("No fixable issues found.")
        print(f"Written to: {args.output}")
        return

    errors, warnings = validate(args.file)

    if args.json:
        result = {
            "file": args.file,
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        if errors:
            print(f"ERRORS ({len(errors)}):")
            for e in errors:
                print(f"  [{e['check']}] {e['message']}")
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"  [{w['check']}] {w['message']}")
        if not errors and not warnings:
            print("VALID: No issues found.")
        elif not errors:
            print(f"\nRESULT: Valid (with {len(warnings)} warning(s))")
        else:
            print(f"\nRESULT: INVALID ({len(errors)} error(s), {len(warnings)} warning(s))")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
