#!/usr/bin/env python3
"""Create new MSPDI XML project plans from JSON input or CLI arguments.

Usage:
    python3 mspdi_create.py --output plan.xml --title "My Project" --start 2026-04-15
    python3 mspdi_create.py --output plan.xml --from-json plan.json
    python3 mspdi_create.py --output plan.xml --from-template custom_template.xml --title "New"
"""

import sys
import os
import argparse
import json
import copy
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from helpers.mspdi_ns import (
    NS, tag, get_text, set_text, get_int, write_mspdi, parse_mspdi
)
from helpers.duration_utils import days_to_pt, hours_to_pt
from mspdi_validate import validate

# Default template location
_TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "templates", "minimal_mspdi"
)
_DEFAULT_TEMPLATE = os.path.join(_TEMPLATE_DIR, "project.xml")

# Register namespace
ET.register_namespace("", NS)


def _add_working_days(start_date, days):
    """Add working days (Mon-Fri) to a date."""
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon=0 to Fri=4
            added += 1
    return current


def _generate_wbs(tasks_data):
    """Generate WBS codes from outline levels.

    Uses a counter stack: outline_level -> current count.
    """
    counters = [0]  # stack of counters per level

    for task in tasks_data:
        ol = task.get("outline_level", 1)

        # Extend or trim the counter stack
        while len(counters) <= ol:
            counters.append(0)
        while len(counters) > ol + 1:
            counters.pop()

        counters[ol] += 1
        # Reset deeper levels
        for i in range(ol + 1, len(counters)):
            counters[i] = 0

        task["_wbs"] = ".".join(str(counters[i]) for i in range(1, ol + 1))


def _detect_summary_tasks(tasks_data):
    """Mark tasks as summary if they have children (deeper outline level follows)."""
    for i, task in enumerate(tasks_data):
        ol = task.get("outline_level", 1)
        # Check if next task has deeper level
        if i + 1 < len(tasks_data):
            next_ol = tasks_data[i + 1].get("outline_level", 1)
            task["_summary"] = next_ol > ol
        else:
            task["_summary"] = False


def create_from_json(json_data, template_path=None):
    """Create MSPDI XML from a JSON structure.

    JSON format:
    {
        "title": "Project Name",
        "start": "2026-04-15T08:00:00",
        "tasks": [
            {"name": "Phase 1", "outline_level": 1, "start": "2026-04-15", "duration_days": 20},
            {"name": "Task 1.1", "outline_level": 2, "start": "2026-04-15", "duration_days": 10},
            {"name": "Milestone", "outline_level": 2, "milestone": true, "start": "2026-04-25"}
        ],
        "resources": [
            {"name": "Engineer A", "type": "work"}
        ]
    }
    """
    template = template_path or _DEFAULT_TEMPLATE
    tree = parse_mspdi(template)
    root = tree.getroot()

    # Set project properties
    title = json_data.get("title", "New Project")
    start = json_data.get("start", datetime.now().strftime("%Y-%m-%dT08:00:00"))
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    set_text(root, "Name", title)
    set_text(root, "Title", title)
    set_text(root, "CreationDate", now)
    set_text(root, "LastSaved", now)
    set_text(root, "StartDate", start)
    set_text(root, "CurrentDate", now)

    # Process tasks
    tasks_data = json_data.get("tasks", [])
    _generate_wbs(tasks_data)
    _detect_summary_tasks(tasks_data)

    # Find Tasks section
    tasks_section = root.find(tag("Tasks"))
    if tasks_section is None:
        tasks_section = ET.SubElement(root, tag("Tasks"))

    # Update project summary task (UID=0)
    summary_task = tasks_section.find(tag("Task"))
    if summary_task is not None:
        set_text(summary_task, "Name", title)
        set_text(summary_task, "Start", start)

    # Track latest finish for project finish date
    latest_finish = start
    uid_counter = 1

    for task_data in tasks_data:
        task_elem = ET.SubElement(tasks_section, tag("Task"))

        uid = uid_counter
        uid_counter += 1

        name = task_data.get("name", "")
        ol = task_data.get("outline_level", 1)
        wbs = task_data.get("_wbs", "")
        is_summary = task_data.get("_summary", False)
        is_milestone = task_data.get("milestone", False)
        pct = task_data.get("percent_complete", 0)

        task_start = task_data.get("start", start)
        if "T" not in task_start:
            task_start += "T08:00:00"

        duration_days = task_data.get("duration_days", 0)

        if is_milestone:
            duration_days = 0
            task_finish = task_start
            duration_pt = "PT0H0M0S"
        elif duration_days > 0:
            start_dt = datetime.fromisoformat(task_start)
            finish_dt = _add_working_days(start_dt, duration_days)
            finish_dt = finish_dt.replace(hour=17, minute=0, second=0)
            task_finish = finish_dt.strftime("%Y-%m-%dT%H:%M:%S")
            duration_pt = days_to_pt(duration_days)
        else:
            task_finish = task_start
            duration_pt = "PT0H0M0S"

        if task_finish > latest_finish:
            latest_finish = task_finish

        set_text(task_elem, "UID", str(uid))
        set_text(task_elem, "ID", str(uid))
        set_text(task_elem, "Name", name)
        set_text(task_elem, "WBS", wbs)
        set_text(task_elem, "OutlineLevel", str(ol))
        set_text(task_elem, "Start", task_start)
        set_text(task_elem, "Finish", task_finish)
        set_text(task_elem, "Duration", duration_pt)
        set_text(task_elem, "PercentComplete", str(int(pct)))
        set_text(task_elem, "Summary", "1" if is_summary else "0")
        set_text(task_elem, "Milestone", "1" if is_milestone else "0")

        notes = task_data.get("notes", "")
        if notes:
            set_text(task_elem, "Notes", notes)

    # Set project finish date
    set_text(root, "FinishDate", latest_finish)
    if summary_task is not None:
        set_text(summary_task, "Finish", latest_finish)

    # Process resources
    resources_data = json_data.get("resources", [])
    resources_section = root.find(tag("Resources"))
    if resources_section is None:
        resources_section = ET.SubElement(root, tag("Resources"))

    res_uid = 1
    for res_data in resources_data:
        res_elem = ET.SubElement(resources_section, tag("Resource"))
        set_text(res_elem, "UID", str(res_uid))
        set_text(res_elem, "ID", str(res_uid))
        set_text(res_elem, "Name", res_data.get("name", ""))
        res_type = res_data.get("type", "work").lower()
        type_val = {"work": "1", "material": "0", "cost": "2"}.get(res_type, "1")
        set_text(res_elem, "Type", type_val)
        res_uid += 1

    return tree


def create_from_cli(title, start, template_path=None):
    """Create a minimal project plan from CLI arguments."""
    json_data = {
        "title": title,
        "start": start if "T" in start else start + "T08:00:00",
        "tasks": [],
        "resources": [],
    }
    return create_from_json(json_data, template_path)


def main():
    parser = argparse.ArgumentParser(
        description="Create new MSPDI XML project plans"
    )
    parser.add_argument("--output", required=True, help="Output XML file path")
    parser.add_argument("--title", default="New Project", help="Project title")
    parser.add_argument("--start", default=None, help="Project start date (YYYY-MM-DD)")
    parser.add_argument("--from-json", default=None, help="JSON file with project data")
    parser.add_argument("--from-template", default=None, help="Custom MSPDI XML template")
    args = parser.parse_args()

    template = args.from_template

    if args.from_json:
        if not os.path.isfile(args.from_json):
            print(f"Error: JSON file not found: {args.from_json}", file=sys.stderr)
            sys.exit(2)
        with open(args.from_json, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        tree = create_from_json(json_data, template)
    else:
        start = args.start or datetime.now().strftime("%Y-%m-%d")
        tree = create_from_cli(args.title, start, template)

    # Pre-write validate
    import io
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

    # Write output (atomic)
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    write_mspdi(tree, args.output)
    print(f"Created: {args.output}")


if __name__ == "__main__":
    main()
