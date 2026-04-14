#!/usr/bin/env python3
"""Read and analyze Microsoft Project files (.mpp and MSPDI .xml).

Usage:
    python3 mpp_reader.py <file.mpp|file.xml>              # full summary
    python3 mpp_reader.py <file> --json                     # machine-readable JSON
    python3 mpp_reader.py <file> --tasks                    # tasks table
    python3 mpp_reader.py <file> --milestones               # milestones only
    python3 mpp_reader.py <file> --critical-path            # critical path tasks
    python3 mpp_reader.py <file> --resources                # resource list
    python3 mpp_reader.py <file> --wbs                      # WBS tree view
    python3 mpp_reader.py <file> --overdue                  # tasks past due
    python3 mpp_reader.py <file> --summary-level N          # tasks up to outline level N
"""

import sys
import os
import argparse
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from helpers.mspdi_ns import (
    parse_mspdi, findall, get_text, get_int, get_float, tag
)
from helpers.duration_utils import pt_to_hours, format_duration


def _read_mpp(filepath):
    """Read an MPP file using MPXJ (requires JVM)."""
    from helpers.jpype_bootstrap import get_reader

    reader = get_reader()
    project = reader.read(filepath)

    props = project.getProjectProperties()
    data = {
        "project": {
            "title": str(props.getProjectTitle() or ""),
            "start": str(props.getStartDate() or ""),
            "finish": str(props.getFinishDate() or ""),
            "last_saved": str(props.getLastSaved() or ""),
            "author": str(props.getAuthor() or ""),
        },
        "tasks": [],
        "resources": [],
        "assignments": [],
    }

    tasks = project.getTasks()
    for i in range(tasks.size()):
        t = tasks.get(i)
        planned_pct_val = float(str(t.getNumber(4) or 0)) if t.getNumber(4) else None
        gap_pct_val = float(str(t.getNumber(3) or 0)) if t.getNumber(3) else None
        
        task_data = {
            "uid": int(str(t.getUniqueID())) if t.getUniqueID() else 0,
            "id": int(str(t.getID())) if t.getID() else 0,
            "name": str(t.getName() or ""),
            "wbs": str(t.getWBS() or ""),
            "outline_level": int(str(t.getOutlineLevel())) if t.getOutlineLevel() else 0,
            "start": str(t.getStart() or ""),
            "finish": str(t.getFinish() or ""),
            "duration": str(t.getDuration() or ""),
            "percent_complete": float(str(t.getPercentageComplete())) if t.getPercentageComplete() else 0.0,
            "summary": bool(t.getSummary()) if t.getSummary() is not None else False,
            "milestone": bool(t.getMilestone()) if t.getMilestone() is not None else False,
            "critical": bool(t.getCritical()) if t.getCritical() is not None else False,
            "notes": str(t.getNotes() or ""),
            "baseline_start": str(t.getBaselineStart() or ""),
            "baseline_finish": str(t.getBaselineFinish() or ""),
            "finish_variance": str(t.getFinishVariance() or ""),
            "planned_pct": planned_pct_val,
            "gap_pct": gap_pct_val,
            "planned_pct_source": "mpp" if planned_pct_val is not None else "",
            "gap_pct_source": "mpp" if gap_pct_val is not None else "",
        }
        data["tasks"].append(task_data)

    resources = project.getResources()
    for i in range(resources.size()):
        r = resources.get(i)
        res_data = {
            "uid": int(str(r.getUniqueID())) if r.getUniqueID() else 0,
            "id": int(str(r.getID())) if r.getID() else 0,
            "name": str(r.getName() or ""),
            "type": str(r.getType() or ""),
        }
        data["resources"].append(res_data)

    assignments = project.getResourceAssignments()
    for i in range(assignments.size()):
        a = assignments.get(i)
        assn_data = {
            "uid": int(str(a.getUniqueID())) if a.getUniqueID() else 0,
            "task_uid": int(str(a.getTask().getUniqueID())) if a.getTask() and a.getTask().getUniqueID() else 0,
            "resource_uid": int(str(a.getResource().getUniqueID())) if a.getResource() and a.getResource().getUniqueID() else 0,
        }
        data["assignments"].append(assn_data)

    return data


def _read_xml(filepath):
    """Read an MSPDI XML file using ElementTree (no JVM needed)."""
    tree = parse_mspdi(filepath)
    root = tree.getroot()

    data = {
        "project": {
            "title": get_text(root, "Title"),
            "start": get_text(root, "StartDate"),
            "finish": get_text(root, "FinishDate"),
            "last_saved": get_text(root, "LastSaved"),
            "author": get_text(root, "Author"),
        },
        "tasks": [],
        "resources": [],
        "assignments": [],
    }

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
            "percent_complete": get_float(task_elem, "PercentComplete"),
            "summary": get_int(task_elem, "Summary") == 1,
            "milestone": get_int(task_elem, "Milestone") == 1,
            "critical": get_int(task_elem, "Critical") == 1,
            "notes": get_text(task_elem, "Notes"),
            "baseline_start": get_text(task_elem, "BaselineStart") or "",
            "baseline_finish": get_text(task_elem, "BaselineFinish") or "",
            "finish_variance": "",
            "planned_pct": None,
            "gap_pct": None,
            "planned_pct_source": "",
            "gap_pct_source": "",
        }
        data["tasks"].append(task_data)

    for res_elem in findall(root, "Resources/Resource"):
        data["resources"].append({
            "uid": get_int(res_elem, "UID"),
            "id": get_int(res_elem, "ID"),
            "name": get_text(res_elem, "Name"),
            "type": get_text(res_elem, "Type"),
        })

    for assn_elem in findall(root, "Assignments/Assignment"):
        data["assignments"].append({
            "uid": get_int(assn_elem, "UID"),
            "task_uid": get_int(assn_elem, "TaskUID"),
            "resource_uid": get_int(assn_elem, "ResourceUID"),
        })

    return data


def read_project(filepath):
    """Read a project file, auto-detecting format."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mpp":
        return _read_mpp(filepath)
    elif ext in (".xml", ".mspdi"):
        return _read_xml(filepath)
    else:
        # Try XML first, fall back to MPP
        try:
            return _read_xml(filepath)
        except Exception:
            return _read_mpp(filepath)


def _compute_stats(data):
    """Compute summary statistics from project data."""
    tasks = data["tasks"]
    leaf_tasks = [t for t in tasks if not t["summary"]]
    summary_tasks = [t for t in tasks if t["summary"]]
    milestones = [t for t in tasks if t.get("milestone")]
    critical = [t for t in tasks if t.get("critical")]

    now = datetime.now().isoformat()
    overdue = [
        t for t in leaf_tasks
        if t.get("finish") and t["finish"] < now and t["percent_complete"] < 100
    ]

    complete = [t for t in leaf_tasks if t["percent_complete"] >= 100]
    in_progress = [t for t in leaf_tasks if 0 < t["percent_complete"] < 100]
    not_started = [t for t in leaf_tasks if t["percent_complete"] == 0]

    return {
        "total_tasks": len(tasks),
        "leaf_tasks": len(leaf_tasks),
        "summary_tasks": len(summary_tasks),
        "milestones": len(milestones),
        "critical_path": len(critical),
        "complete": len(complete),
        "in_progress": len(in_progress),
        "not_started": len(not_started),
        "overdue": len(overdue),
    }


def _print_summary(data):
    """Print human-readable project summary."""
    proj = data["project"]
    stats = _compute_stats(data)

    print(f"{'='*60}")
    print(f"Project: {proj['title'] or '(untitled)'}")
    print(f"{'='*60}")
    print(f"Start:      {proj['start']}")
    print(f"Finish:     {proj['finish']}")
    print(f"Last Saved: {proj['last_saved']}")
    print()
    print(f"Total Tasks:     {stats['total_tasks']}")
    print(f"  Summary:       {stats['summary_tasks']}")
    print(f"  Leaf:          {stats['leaf_tasks']}")
    print(f"  Milestones:    {stats['milestones']}")
    print(f"  Critical Path: {stats['critical_path']}")
    print()
    print(f"Status:")
    print(f"  Complete:      {stats['complete']}")
    print(f"  In Progress:   {stats['in_progress']}")
    print(f"  Not Started:   {stats['not_started']}")
    print(f"  Overdue:       {stats['overdue']}")
    print()
    print(f"Resources:       {len(data['resources'])}")
    print(f"Assignments:     {len(data['assignments'])}")


def _print_tasks(data, summary_level=None):
    """Print tasks as a table."""
    tasks = data["tasks"]
    if summary_level is not None:
        tasks = [t for t in tasks if t["outline_level"] <= summary_level]

    print(f"{'ID':>4} {'OL':>2} {'WBS':<12} {'%':>5} {'S':1} {'M':1} {'C':1} {'Start':<20} {'Finish':<20} {'Name'}")
    print("-" * 120)
    for t in tasks:
        s = "S" if t["summary"] else " "
        m = "M" if t.get("milestone") else " "
        c = "C" if t.get("critical") else " "
        pct = f"{t['percent_complete']:.0f}%"
        print(f"{t['id']:>4} {t['outline_level']:>2} {t['wbs']:<12} {pct:>5} {s} {m} {c} {t['start'][:19]:<20} {t['finish'][:19]:<20} {t['name']}")


def _print_milestones(data):
    """Print milestones only."""
    milestones = [t for t in data["tasks"] if t.get("milestone")]
    if not milestones:
        print("No milestones found.")
        return

    print(f"{'ID':>4} {'WBS':<12} {'%':>5} {'Date':<20} {'Name'}")
    print("-" * 80)
    for t in milestones:
        date = t.get("finish") or t.get("start") or ""
        pct = f"{t['percent_complete']:.0f}%"
        print(f"{t['id']:>4} {t['wbs']:<12} {pct:>5} {date[:19]:<20} {t['name']}")


def _print_critical_path(data):
    """Print critical path tasks."""
    critical = [t for t in data["tasks"] if t.get("critical") and not t["summary"]]
    if not critical:
        print("No critical path tasks found.")
        return

    print(f"{'ID':>4} {'WBS':<12} {'%':>5} {'Start':<20} {'Finish':<20} {'Name'}")
    print("-" * 100)
    for t in critical:
        pct = f"{t['percent_complete']:.0f}%"
        print(f"{t['id']:>4} {t['wbs']:<12} {pct:>5} {t['start'][:19]:<20} {t['finish'][:19]:<20} {t['name']}")


def _print_resources(data):
    """Print resource list."""
    resources = data["resources"]
    if not resources:
        print("No resources found.")
        return

    print(f"{'ID':>4} {'Type':<10} {'Name'}")
    print("-" * 40)
    for r in resources:
        print(f"{r['id']:>4} {r['type']:<10} {r['name']}")


def _print_wbs(data, summary_level=None):
    """Print WBS tree view."""
    tasks = data["tasks"]
    if summary_level is not None:
        tasks = [t for t in tasks if t["outline_level"] <= summary_level]

    for t in tasks:
        indent = "  " * t["outline_level"]
        pct = f"[{t['percent_complete']:.0f}%]"
        flags = ""
        if t.get("milestone"):
            flags += " (milestone)"
        if t.get("critical"):
            flags += " (critical)"
        print(f"{indent}{t['wbs']} {t['name']} {pct}{flags}")


def _print_overdue(data):
    """Print overdue tasks."""
    now = datetime.now().isoformat()
    overdue = [
        t for t in data["tasks"]
        if not t["summary"] and t.get("finish") and t["finish"] < now and t["percent_complete"] < 100
    ]

    if not overdue:
        print("No overdue tasks found.")
        return

    print(f"{'ID':>4} {'WBS':<12} {'%':>5} {'Finish':<20} {'Name'}")
    print("-" * 80)
    for t in sorted(overdue, key=lambda x: x["finish"]):
        pct = f"{t['percent_complete']:.0f}%"
        print(f"{t['id']:>4} {t['wbs']:<12} {pct:>5} {t['finish'][:19]:<20} {t['name']}")


def main():
    parser = argparse.ArgumentParser(
        description="Read and analyze Microsoft Project files (.mpp and MSPDI .xml)"
    )
    parser.add_argument("file", help="Input file path (.mpp or .xml)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--tasks", action="store_true", help="Show tasks table")
    parser.add_argument("--milestones", action="store_true", help="Show milestones only")
    parser.add_argument("--critical-path", action="store_true", help="Show critical path tasks")
    parser.add_argument("--resources", action="store_true", help="Show resource list")
    parser.add_argument("--wbs", action="store_true", help="Show WBS tree view")
    parser.add_argument("--overdue", action="store_true", help="Show overdue tasks")
    parser.add_argument("--summary-level", type=int, default=None,
                        help="Show tasks up to this outline level")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    try:
        data = read_project(args.file)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        data["statistics"] = _compute_stats(data)
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()
    elif args.tasks:
        _print_tasks(data, args.summary_level)
    elif args.milestones:
        _print_milestones(data)
    elif args.critical_path:
        _print_critical_path(data)
    elif args.resources:
        _print_resources(data)
    elif args.wbs:
        _print_wbs(data, args.summary_level)
    elif args.overdue:
        _print_overdue(data)
    else:
        _print_summary(data)


if __name__ == "__main__":
    main()
