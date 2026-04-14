#!/usr/bin/env python3
"""Compare two MPP/MSPDI project plans and report differences.

Usage:
    python3 mpp_diff.py old.xml new.xml              # markdown to stdout
    python3 mpp_diff.py old.xml new.xml --json        # machine-readable JSON
    python3 mpp_diff.py old.xml new.xml -o diff.md    # write markdown to file
"""

import sys
import os
import argparse
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from mpp_reader import read_project

PROGRESS_THRESHOLD = 10  # % change to report


def _index_by_uid(tasks):
    """Build {uid: task} dict for O(1) lookup."""
    return {t["uid"]: t for t in tasks}


def diff_projects(old_data, new_data, today=None):
    """Compare two project datasets. Returns a diff dict."""
    today = today or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    today_short = today[:10]

    old_tasks = old_data["tasks"]
    new_tasks = new_data["tasks"]
    old_by_uid = _index_by_uid(old_tasks)
    new_by_uid = _index_by_uid(new_tasks)

    old_leaf = [t for t in old_tasks if not t.get("summary")]
    new_leaf = [t for t in new_tasks if not t.get("summary")]

    old_uids = set(old_by_uid.keys())
    new_uids = set(new_by_uid.keys())

    # Added / removed tasks
    added = [new_by_uid[uid] for uid in sorted(new_uids - old_uids)]
    removed = [old_by_uid[uid] for uid in sorted(old_uids - new_uids)]

    # Progress changes (leaf tasks only, >= threshold)
    progress_changes = []
    for uid in old_uids & new_uids:
        old_t = old_by_uid[uid]
        new_t = new_by_uid[uid]
        if old_t.get("summary") or new_t.get("summary"):
            continue
        old_pct = old_t.get("percent_complete", 0)
        new_pct = new_t.get("percent_complete", 0)
        diff = new_pct - old_pct
        if abs(diff) >= PROGRESS_THRESHOLD:
            progress_changes.append({
                "uid": uid,
                "name": new_t.get("name", ""),
                "wbs": new_t.get("wbs", ""),
                "old_pct": old_pct,
                "new_pct": new_pct,
                "diff": diff,
            })
    progress_changes.sort(key=lambda x: -abs(x["diff"]))

    # Date changes (finish date shifts)
    date_changes = []
    for uid in old_uids & new_uids:
        old_t = old_by_uid[uid]
        new_t = new_by_uid[uid]
        old_fin = (old_t.get("finish") or "")[:10]
        new_fin = (new_t.get("finish") or "")[:10]
        if old_fin and new_fin and old_fin != new_fin:
            try:
                delta = (datetime.fromisoformat(new_fin) -
                         datetime.fromisoformat(old_fin)).days
            except ValueError:
                delta = 0
            if abs(delta) >= 1:
                date_changes.append({
                    "uid": uid,
                    "name": new_t.get("name", ""),
                    "wbs": new_t.get("wbs", ""),
                    "old_finish": old_fin,
                    "new_finish": new_fin,
                    "delta_days": delta,
                })
    date_changes.sort(key=lambda x: -abs(x["delta_days"]))

    # Overdue trend
    def count_overdue(tasks, cutoff):
        return len([t for t in tasks if not t.get("summary")
                    and (t.get("finish") or "")[:10] < cutoff
                    and t.get("percent_complete", 0) < 100])

    old_overdue = count_overdue(old_tasks, today_short)
    new_overdue = count_overdue(new_tasks, today_short)

    return {
        "old_title": old_data["project"].get("title", ""),
        "new_title": new_data["project"].get("title", ""),
        "summary": {
            "old_total": len(old_tasks),
            "new_total": len(new_tasks),
            "old_leaf": len(old_leaf),
            "new_leaf": len(new_leaf),
            "added": len(added),
            "removed": len(removed),
            "old_overdue": old_overdue,
            "new_overdue": new_overdue,
            "progress_changes": len(progress_changes),
            "date_changes": len(date_changes),
        },
        "added": [{"uid": t["uid"], "name": t.get("name", ""), "wbs": t.get("wbs", ""),
                    "start": (t.get("start") or "")[:10], "finish": (t.get("finish") or "")[:10]}
                   for t in added if not t.get("summary")],
        "removed": [{"uid": t["uid"], "name": t.get("name", ""), "wbs": t.get("wbs", "")}
                     for t in removed if not t.get("summary")],
        "progress_changes": progress_changes,
        "date_changes": date_changes[:30],
    }


def format_markdown(diff):
    """Render diff as markdown."""
    s = diff["summary"]
    lines = [
        f"# MPP Version Diff",
        f"",
        f"**{diff['old_title']}** → **{diff['new_title']}**",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Old | New | Δ |",
        f"|--------|-----|-----|---|",
        f"| Total tasks | {s['old_total']} | {s['new_total']} | {s['new_total']-s['old_total']:+d} |",
        f"| Leaf tasks | {s['old_leaf']} | {s['new_leaf']} | {s['new_leaf']-s['old_leaf']:+d} |",
        f"| Overdue (leaf) | {s['old_overdue']} | {s['new_overdue']} | {s['new_overdue']-s['old_overdue']:+d} |",
        f"| Tasks added | | | +{s['added']} |",
        f"| Tasks removed | | | -{s['removed']} |",
        f"| Progress changes (Δ≥{PROGRESS_THRESHOLD}%) | | | {s['progress_changes']} |",
        f"| Date changes | | | {s['date_changes']} |",
        f"",
    ]

    if diff["progress_changes"]:
        lines.append(f"## Progress Changes (Δ≥{PROGRESS_THRESHOLD}%)")
        lines.append(f"")
        lines.append(f"| WBS | Task | Old % | New % | Δ |")
        lines.append(f"|-----|------|-------|-------|---|")
        for c in diff["progress_changes"][:20]:
            lines.append(f"| {c['wbs']} | {c['name']} | {c['old_pct']:.0f}% | {c['new_pct']:.0f}% | {c['diff']:+.0f}% |")
        if len(diff["progress_changes"]) > 20:
            lines.append(f"| ... | *{len(diff['progress_changes'])-20} more* | | | |")
        lines.append(f"")

    if diff["added"]:
        lines.append(f"## Added Tasks ({len(diff['added'])} leaf)")
        lines.append(f"")
        lines.append(f"| WBS | Task | Start | Finish |")
        lines.append(f"|-----|------|-------|--------|")
        for t in diff["added"][:20]:
            lines.append(f"| {t['wbs']} | {t['name']} | {t['start']} | {t['finish']} |")
        if len(diff["added"]) > 20:
            lines.append(f"| ... | *{len(diff['added'])-20} more* | | |")
        lines.append(f"")

    if diff["removed"]:
        lines.append(f"## Removed Tasks ({len(diff['removed'])} leaf)")
        lines.append(f"")
        lines.append(f"| WBS | Task |")
        lines.append(f"|-----|------|")
        for t in diff["removed"][:20]:
            lines.append(f"| {t['wbs']} | {t['name']} |")
        lines.append(f"")

    if diff["date_changes"]:
        lines.append(f"## Date Changes (top 20)")
        lines.append(f"")
        lines.append(f"| WBS | Task | Old Finish | New Finish | Δ days |")
        lines.append(f"|-----|------|-----------|-----------|--------|")
        for c in diff["date_changes"][:20]:
            lines.append(f"| {c['wbs']} | {c['name']} | {c['old_finish']} | {c['new_finish']} | {c['delta_days']:+d} |")
        lines.append(f"")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare two MPP/MSPDI project plans")
    parser.add_argument("old", help="Old/baseline file (.mpp or .xml)")
    parser.add_argument("new", help="New/current file (.mpp or .xml)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    parser.add_argument("-o", "--output", help="Write output to file instead of stdout")
    args = parser.parse_args()

    for f in [args.old, args.new]:
        if not os.path.isfile(f):
            print(f"Error: File not found: {f}", file=sys.stderr)
            sys.exit(2)

    try:
        old_data = read_project(args.old)
        new_data = read_project(args.new)
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        sys.exit(1)

    diff = diff_projects(old_data, new_data)

    if args.json:
        output = json.dumps(diff, indent=2, ensure_ascii=False)
    else:
        output = format_markdown(diff)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved: {args.output}")
    else:
        print(output)

    s = diff["summary"]
    print(f"\n--- Diff: {s['added']} added, {s['removed']} removed, "
          f"{s['progress_changes']} progress changes, "
          f"overdue {s['old_overdue']}→{s['new_overdue']}", file=sys.stderr)


if __name__ == "__main__":
    main()
