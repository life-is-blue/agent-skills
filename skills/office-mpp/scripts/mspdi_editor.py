#!/usr/bin/env python3
"""Edit tasks in existing MSPDI XML files. Supports update, delete, add, and batch operations.

Usage:
    # Update task by UID
    python3 mspdi_editor.py input.xml --output out.xml --update-task --uid 5 --percent-complete 90

    # Update task by name
    python3 mspdi_editor.py input.xml --output out.xml --update-task --name "Web App" --finish "2026-04-20T17:00:00"

    # Batch update from JSON
    python3 mspdi_editor.py input.xml --output out.xml --batch-update updates.json

    # Delete a task
    python3 mspdi_editor.py input.xml --output out.xml --delete-task --uid 5

    # Add a new task
    python3 mspdi_editor.py input.xml --output out.xml --add-task --name "New Task" --outline-level 3 --after-uid 5 --start "2026-04-15" --duration-days 5
"""

import sys
import os
import argparse
import json
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))

from helpers.mspdi_ns import (
    NS, tag, get_text, set_text, get_int, get_float,
    findall, find, parse_mspdi, write_mspdi
)
from helpers.duration_utils import days_to_pt, pt_to_hours
from mspdi_validate import validate

ET.register_namespace("", NS)


def _find_task_by_uid(root, uid):
    """Find a Task element by UID."""
    for task_elem in findall(root, "Tasks/Task"):
        if get_int(task_elem, "UID") == uid:
            return task_elem
    return None


def _find_task_by_name(root, name):
    """Find a Task element by Name (first match)."""
    for task_elem in findall(root, "Tasks/Task"):
        if get_text(task_elem, "Name") == name:
            return task_elem
    return None


def _get_max_uid(root):
    """Get the maximum Task UID in the project."""
    max_uid = 0
    for task_elem in findall(root, "Tasks/Task"):
        uid = get_int(task_elem, "UID")
        if uid > max_uid:
            max_uid = uid
    return max_uid


def _get_max_id(root):
    """Get the maximum Task ID in the project."""
    max_id = 0
    for task_elem in findall(root, "Tasks/Task"):
        tid = get_int(task_elem, "ID")
        if tid > max_id:
            max_id = tid
    return max_id


def _update_task_fields(task_elem, updates):
    """Apply field updates to a task element.

    Supported fields:
        name, start, finish, duration, duration_days, percent_complete,
        actual_start, actual_finish, notes, milestone, critical
    """
    field_map = {
        "name": "Name",
        "start": "Start",
        "finish": "Finish",
        "duration": "Duration",
        "percent_complete": "PercentComplete",
        "actual_start": "ActualStart",
        "actual_finish": "ActualFinish",
        "notes": "Notes",
    }

    for key, value in updates.items():
        if key in field_map:
            set_text(task_elem, field_map[key], str(value))
        elif key == "duration_days":
            set_text(task_elem, "Duration", days_to_pt(float(value)))
        elif key == "milestone":
            set_text(task_elem, "Milestone", "1" if value else "0")
        elif key == "critical":
            set_text(task_elem, "Critical", "1" if value else "0")

    return task_elem


def _recalculate_summary(root):
    """Recalculate summary task rollups (PercentComplete, Start, Finish).

    Summary tasks aggregate values from their direct children:
    - Start = earliest child Start
    - Finish = latest child Finish
    - PercentComplete = weighted average by duration
    """
    tasks = findall(root, "Tasks/Task")

    # Build parent-child relationships from outline levels
    # Tasks are in document order; a task's children are subsequent tasks with deeper outline level
    task_list = []
    for t in tasks:
        task_list.append({
            "elem": t,
            "uid": get_int(t, "UID"),
            "outline_level": get_int(t, "OutlineLevel"),
            "summary": get_int(t, "Summary") == 1,
            "children_indices": [],
        })

    # Build children indices
    for i, task in enumerate(task_list):
        if not task["summary"]:
            continue
        my_level = task["outline_level"]
        for j in range(i + 1, len(task_list)):
            child = task_list[j]
            if child["outline_level"] <= my_level:
                break
            if child["outline_level"] == my_level + 1:
                task["children_indices"].append(j)

    # Bottom-up recalculation (reverse order)
    for i in reversed(range(len(task_list))):
        task = task_list[i]
        if not task["summary"] or not task["children_indices"]:
            continue

        children = [task_list[j] for j in task["children_indices"]]
        child_elems = [c["elem"] for c in children]

        # Earliest start
        starts = [get_text(ce, "Start") for ce in child_elems if get_text(ce, "Start")]
        if starts:
            set_text(task["elem"], "Start", min(starts))

        # Latest finish
        finishes = [get_text(ce, "Finish") for ce in child_elems if get_text(ce, "Finish")]
        if finishes:
            set_text(task["elem"], "Finish", max(finishes))

        # Weighted average percent complete
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


def update_task(root, uid=None, name=None, **updates):
    """Update a task by UID or Name."""
    if uid is not None:
        task_elem = _find_task_by_uid(root, uid)
        if task_elem is None:
            raise ValueError(f"Task with UID={uid} not found")
    elif name is not None:
        task_elem = _find_task_by_name(root, name)
        if task_elem is None:
            raise ValueError(f"Task with Name='{name}' not found")
    else:
        raise ValueError("Must specify --uid or --name")

    _update_task_fields(task_elem, updates)
    _recalculate_summary(root)
    return task_elem


def delete_task(root, uid):
    """Delete a task and its orphaned assignments."""
    tasks_section = find(root, "Tasks")
    if tasks_section is None:
        raise ValueError("No Tasks section found")

    task_elem = _find_task_by_uid(root, uid)
    if task_elem is None:
        raise ValueError(f"Task with UID={uid} not found")

    # Also delete child tasks (deeper outline level following this task)
    task_ol = get_int(task_elem, "OutlineLevel")
    tasks_to_delete = [task_elem]
    all_tasks = list(findall(root, "Tasks/Task"))
    idx = all_tasks.index(task_elem)

    for i in range(idx + 1, len(all_tasks)):
        child_ol = get_int(all_tasks[i], "OutlineLevel")
        if child_ol <= task_ol:
            break
        tasks_to_delete.append(all_tasks[i])

    deleted_uids = set()
    for t in tasks_to_delete:
        deleted_uids.add(get_int(t, "UID"))
        tasks_section.remove(t)

    # Remove orphaned assignments
    assignments_section = find(root, "Assignments")
    if assignments_section is not None:
        for assn in list(findall(root, "Assignments/Assignment")):
            if get_int(assn, "TaskUID") in deleted_uids:
                assignments_section.remove(assn)

    _recalculate_summary(root)
    return deleted_uids


def add_task(root, name, outline_level, after_uid=None, start=None, duration_days=0, milestone=False):
    """Add a new task after the specified UID."""
    tasks_section = find(root, "Tasks")
    if tasks_section is None:
        raise ValueError("No Tasks section found")

    new_uid = _get_max_uid(root) + 1
    new_id = _get_max_id(root) + 1

    task_elem = ET.Element(tag("Task"))
    set_text(task_elem, "UID", str(new_uid))
    set_text(task_elem, "ID", str(new_id))
    set_text(task_elem, "Name", name)
    set_text(task_elem, "OutlineLevel", str(outline_level))

    if start:
        if "T" not in start:
            start += "T08:00:00"
        set_text(task_elem, "Start", start)

        if milestone:
            set_text(task_elem, "Finish", start)
            set_text(task_elem, "Duration", "PT0H0M0S")
            set_text(task_elem, "Milestone", "1")
        elif duration_days > 0:
            from mspdi_create import _add_working_days
            from datetime import datetime as dt
            start_dt = dt.fromisoformat(start)
            finish_dt = _add_working_days(start_dt, duration_days)
            finish_dt = finish_dt.replace(hour=17, minute=0, second=0)
            set_text(task_elem, "Finish", finish_dt.strftime("%Y-%m-%dT%H:%M:%S"))
            set_text(task_elem, "Duration", days_to_pt(duration_days))

    set_text(task_elem, "PercentComplete", "0")
    set_text(task_elem, "Summary", "0")

    # Insert after specified UID, or at end
    if after_uid is not None:
        all_tasks = list(findall(root, "Tasks/Task"))
        insert_idx = None
        for i, t in enumerate(all_tasks):
            if get_int(t, "UID") == after_uid:
                insert_idx = i + 1
                break

        if insert_idx is not None:
            # Find position in tasks_section children
            section_children = list(tasks_section)
            if insert_idx < len(section_children):
                ref_elem = section_children[insert_idx]
                # Insert before the reference element
                idx_in_section = list(tasks_section).index(ref_elem)
                tasks_section.insert(idx_in_section, task_elem)
            else:
                tasks_section.append(task_elem)
        else:
            tasks_section.append(task_elem)
    else:
        tasks_section.append(task_elem)

    _recalculate_summary(root)
    return new_uid


def batch_update(root, updates_list):
    """Apply multiple task updates from a list of dicts.

    Each dict must have 'uid' and/or 'name', plus update fields.
    """
    for update in updates_list:
        uid = update.pop("uid", None)
        name = update.pop("name", None)
        update_task(root, uid=uid, name=name, **update)


def main():
    parser = argparse.ArgumentParser(
        description="Edit tasks in MSPDI XML files"
    )
    parser.add_argument("input", help="Input MSPDI XML file")
    parser.add_argument("--output", required=True, help="Output XML file path")

    # Operation group
    op_group = parser.add_mutually_exclusive_group(required=True)
    op_group.add_argument("--update-task", action="store_true", help="Update a task")
    op_group.add_argument("--delete-task", action="store_true", help="Delete a task")
    op_group.add_argument("--add-task", action="store_true", help="Add a new task")
    op_group.add_argument("--batch-update", metavar="JSON_FILE", help="Batch update from JSON")

    # Task identification
    parser.add_argument("--uid", type=int, help="Task UID")
    parser.add_argument("--name", help="Task name")

    # Update fields
    parser.add_argument("--percent-complete", type=float, help="Percent complete (0-100)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--finish", help="Finish date")
    parser.add_argument("--actual-start", help="Actual start date")
    parser.add_argument("--actual-finish", help="Actual finish date")
    parser.add_argument("--duration-days", type=float, help="Duration in working days")
    parser.add_argument("--notes", help="Task notes")
    parser.add_argument("--task-name", help="New task name (for update)")
    parser.add_argument("--milestone", action="store_true", help="Mark as milestone")

    # Add task specific
    parser.add_argument("--outline-level", type=int, help="Outline level for new task")
    parser.add_argument("--after-uid", type=int, help="Insert after this UID")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    tree = parse_mspdi(args.input)
    root = tree.getroot()

    try:
        if args.update_task:
            updates = {}
            if args.percent_complete is not None:
                updates["percent_complete"] = int(args.percent_complete)
            if args.start:
                updates["start"] = args.start
            if args.finish:
                updates["finish"] = args.finish
            if args.actual_start:
                updates["actual_start"] = args.actual_start
            if args.actual_finish:
                updates["actual_finish"] = args.actual_finish
            if args.duration_days is not None:
                updates["duration_days"] = args.duration_days
            if args.notes:
                updates["notes"] = args.notes
            if args.task_name:
                updates["name"] = args.task_name

            task_elem = update_task(root, uid=args.uid, name=args.name, **updates)
            task_name = get_text(task_elem, "Name")
            print(f"Updated task: {task_name}")

        elif args.delete_task:
            if args.uid is None:
                print("Error: --uid required for delete", file=sys.stderr)
                sys.exit(2)
            deleted = delete_task(root, args.uid)
            print(f"Deleted {len(deleted)} task(s): UIDs {sorted(deleted)}")

        elif args.add_task:
            if not args.name:
                print("Error: --name required for add", file=sys.stderr)
                sys.exit(2)
            ol = args.outline_level or 1
            new_uid = add_task(
                root, args.name, ol,
                after_uid=args.after_uid,
                start=args.start,
                duration_days=args.duration_days or 0,
                milestone=args.milestone,
            )
            print(f"Added task UID={new_uid}: {args.name}")

        elif args.batch_update:
            if not os.path.isfile(args.batch_update):
                print(f"Error: JSON file not found: {args.batch_update}", file=sys.stderr)
                sys.exit(2)
            with open(args.batch_update, "r", encoding="utf-8") as f:
                updates_list = json.load(f)
            batch_update(root, updates_list)
            print(f"Applied {len(updates_list)} batch updates")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

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

    # Write output (atomic)
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    write_mspdi(tree, args.output)
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
