#!/usr/bin/env python3
"""Extract project data and generate markdown for status.md and todo.md.

Usage:
    python3 mpp_report.py <file.mpp|file.xml> --status     # markdown status fragment
    python3 mpp_report.py <file.mpp|file.xml> --todo        # markdown todo fragment
    python3 mpp_report.py <file.mpp|file.xml> --status --todo  # both
    python3 mpp_report.py <file.mpp|file.xml> --json        # raw data
"""

import sys
import os
import argparse
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from mpp_reader import read_project
from helpers.duration_utils import pt_to_hours, format_duration


def _milestone_status(task, now_str):
    """Determine milestone status icon."""
    pct = task["percent_complete"]
    finish = task.get("finish", "")

    if pct >= 100:
        return "done"
    if finish and finish < now_str:
        return "overdue"
    # At risk: within 7 days and less than 50% complete
    if finish:
        try:
            finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00").split("+")[0])
            now_dt = datetime.now()
            if (finish_dt - now_dt).days <= 7 and pct < 50:
                return "at-risk"
        except ValueError:
            pass
    return "on-track"


def _status_icon(status):
    """Return status icon for markdown."""
    icons = {
        "done": "done",
        "overdue": "OVERDUE",
        "at-risk": "AT RISK",
        "on-track": "on track",
    }
    return icons.get(status, status)


def generate_status(data):
    """Generate markdown status fragment from project data."""
    proj = data["project"]
    tasks = data["tasks"]
    now_str = datetime.now().isoformat()

    # Top-level workstreams (outline level 1)
    workstreams = [t for t in tasks if t["outline_level"] == 1]

    # Milestones
    milestones = [t for t in tasks if t.get("milestone")]

    # Overdue leaf tasks
    leaf_tasks = [t for t in tasks if not t["summary"]]
    overdue = [
        t for t in leaf_tasks
        if t.get("finish") and t["finish"] < now_str and t["percent_complete"] < 100
    ]

    # Critical path tasks that are not complete
    critical_incomplete = [
        t for t in leaf_tasks if t.get("critical") and t["percent_complete"] < 100
    ]

    lines = []
    lines.append(f"## Project Overview\n")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Title | {proj.get('title', '')} |")
    lines.append(f"| Start | {proj.get('start', '')[:10]} |")
    lines.append(f"| Finish | {proj.get('finish', '')[:10]} |")
    lines.append(f"| Total Tasks | {len(tasks)} |")
    lines.append(f"| Leaf Tasks | {len(leaf_tasks)} |")
    lines.append(f"| Overdue | {len(overdue)} |")
    lines.append("")

    # Workstream progress
    if workstreams:
        lines.append(f"## Workstream Progress\n")
        lines.append(f"| # | Workstream | Start | Finish | % Complete | Critical |")
        lines.append(f"|---|-----------|-------|--------|------------|----------|")
        for i, ws in enumerate(workstreams, 1):
            start = ws.get("start", "")[:10]
            finish = ws.get("finish", "")[:10]
            pct = f"{ws['percent_complete']:.0f}%"
            crit = "Yes" if ws.get("critical") else ""
            lines.append(f"| {i} | {ws['name']} | {start} | {finish} | {pct} | {crit} |")
        lines.append("")

    # Milestones
    if milestones:
        lines.append(f"## Milestones\n")
        lines.append(f"| # | Milestone | Target Date | % | Status |")
        lines.append(f"|---|-----------|-------------|---|--------|")
        for i, ms in enumerate(milestones, 1):
            target = ms.get("finish", ms.get("start", ""))[:10]
            pct = f"{ms['percent_complete']:.0f}%"
            status = _status_icon(_milestone_status(ms, now_str))
            lines.append(f"| {i} | {ms['name']} | {target} | {pct} | {status} |")
        lines.append("")

    # Risk indicators
    if overdue or critical_incomplete:
        lines.append(f"## Risk Indicators\n")
        if overdue:
            lines.append(f"**Overdue Tasks ({len(overdue)}):**\n")
            for t in sorted(overdue, key=lambda x: x.get("finish", ""))[:10]:
                lines.append(f"- {t['name']} (due {t.get('finish', '')[:10]}, {t['percent_complete']:.0f}%)")
            lines.append("")
        if critical_incomplete:
            lines.append(f"**Critical Path - Incomplete ({len(critical_incomplete)}):**\n")
            for t in critical_incomplete[:10]:
                lines.append(f"- {t['name']} ({t['percent_complete']:.0f}%, due {t.get('finish', '')[:10]})")
            lines.append("")

    return "\n".join(lines)


def generate_todo(data):
    """Generate markdown todo fragment from project data."""
    tasks = data["tasks"]
    now_str = datetime.now().isoformat()
    now_dt = datetime.now()

    leaf_tasks = [t for t in tasks if not t["summary"]]

    # Active tasks: not complete leaf tasks
    active = [t for t in leaf_tasks if t["percent_complete"] < 100]
    active.sort(key=lambda x: x.get("finish", "9999"))

    # Upcoming milestones (next 30 days)
    milestones = [t for t in tasks if t.get("milestone") and t["percent_complete"] < 100]
    upcoming_milestones = []
    for ms in milestones:
        finish = ms.get("finish", ms.get("start", ""))
        if finish:
            try:
                ms_dt = datetime.fromisoformat(finish.split("+")[0].replace("Z", ""))
                if 0 <= (ms_dt - now_dt).days <= 30:
                    upcoming_milestones.append(ms)
            except ValueError:
                pass

    # Overdue tasks
    overdue = [
        t for t in leaf_tasks
        if t.get("finish") and t["finish"] < now_str and t["percent_complete"] < 100
    ]

    # Near-term: tasks starting in next 14 days
    near_term = []
    for t in active:
        start = t.get("start", "")
        if start:
            try:
                start_dt = datetime.fromisoformat(start.split("+")[0].replace("Z", ""))
                if 0 <= (start_dt - now_dt).days <= 14:
                    near_term.append(t)
            except ValueError:
                pass

    lines = []

    # Active tasks table
    lines.append(f"## Active Tasks ({len(active)})\n")
    lines.append(f"| # | Priority | Task | WBS | Finish | % | Status |")
    lines.append(f"|---|----------|------|-----|--------|---|--------|")
    for i, t in enumerate(active[:30], 1):
        finish = t.get("finish", "")[:10]
        pct = f"{t['percent_complete']:.0f}%"
        wbs = t.get("wbs", "")

        if t.get("finish") and t["finish"] < now_str:
            status = "OVERDUE"
            priority = "High"
        elif t.get("critical"):
            status = "Critical Path"
            priority = "High"
        elif t["percent_complete"] > 0:
            status = "In Progress"
            priority = "Medium"
        else:
            status = "Not Started"
            priority = "Normal"

        lines.append(f"| {i} | {priority} | {t['name']} | {wbs} | {finish} | {pct} | {status} |")
    if len(active) > 30:
        lines.append(f"| ... | | *{len(active) - 30} more tasks* | | | | |")
    lines.append("")

    # Upcoming milestones
    if upcoming_milestones:
        lines.append(f"## Upcoming Milestones (next 30 days)\n")
        lines.append(f"| # | Milestone | Target Date | % |")
        lines.append(f"|---|-----------|-------------|---|")
        for i, ms in enumerate(upcoming_milestones, 1):
            target = ms.get("finish", ms.get("start", ""))[:10]
            pct = f"{ms['percent_complete']:.0f}%"
            lines.append(f"| {i} | {ms['name']} | {target} | {pct} |")
        lines.append("")

    # Blockers / Overdue
    if overdue:
        lines.append(f"## Blockers / Overdue ({len(overdue)})\n")
        lines.append(f"| # | Task | Due Date | % | Days Overdue |")
        lines.append(f"|---|------|----------|---|-------------|")
        for i, t in enumerate(sorted(overdue, key=lambda x: x.get("finish", "")), 1):
            finish = t.get("finish", "")[:10]
            pct = f"{t['percent_complete']:.0f}%"
            try:
                due_dt = datetime.fromisoformat(t["finish"].split("+")[0].replace("Z", ""))
                days_over = (now_dt - due_dt).days
            except ValueError:
                days_over = "?"
            lines.append(f"| {i} | {t['name']} | {finish} | {pct} | {days_over} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate status/todo markdown from project data"
    )
    parser.add_argument("file", help="Input file (.mpp or .xml)")
    parser.add_argument("--status", action="store_true", help="Generate status report")
    parser.add_argument("--todo", action="store_true", help="Generate todo report")
    parser.add_argument("--json", action="store_true", help="Output raw data as JSON")
    args = parser.parse_args()

    if not args.status and not args.todo and not args.json:
        args.status = True
        args.todo = True

    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    try:
        data = read_project(args.file)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()
        return

    if args.status:
        print(generate_status(data))

    if args.todo:
        print(generate_todo(data))


if __name__ == "__main__":
    main()
