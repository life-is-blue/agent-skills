#!/usr/bin/env python3
"""Pure analysis functions for Microsoft Project data.

No I/O — takes the dict from mpp_reader.read_project() and returns diagnostics.

Usage:
    from mpp_analyze import analyze_project
    data = read_project("plan.xml")
    issues = analyze_project(data)
"""

from datetime import datetime
from collections import defaultdict

# Thresholds — tweak here, not buried in code
CONSISTENCY_THRESHOLD = 10   # % difference to flag parent-child mismatch
OVERDUE_CRITICAL_DAYS = 30
OVERDUE_HIGH_DAYS = 14
PROGRESS_DIFF_THRESHOLD = 10  # % change to flag in diff


def analyze_project(data, today=None):
    """Compute all diagnostic metrics from project data.

    Args:
        data: dict from read_project() with "project" and "tasks" keys
        today: ISO date string (default: now). Used as overdue cutoff.

    Returns:
        dict with keys: overdue, should_started, no_predecessors,
        inconsistent_parents, summary
    """
    today = today or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    today_short = today[:10]

    tasks = data["tasks"]
    leaf = [t for t in tasks if not t.get("summary")]
    summary_tasks = [t for t in tasks if t.get("summary")]

    # --- Overdue leaf tasks ---
    overdue = []
    for t in leaf:
        finish = (t.get("finish") or "")[:10]
        if finish and finish < today_short and t.get("percent_complete", 0) < 100:
            try:
                days = (datetime.fromisoformat(today_short) -
                        datetime.fromisoformat(finish)).days
            except ValueError:
                days = 0
            overdue.append({**t, "days_overdue": days})
    overdue.sort(key=lambda x: -x["days_overdue"])

    # --- Should-have-started but 0% ---
    should_started = []
    for t in leaf:
        start = (t.get("start") or "")[:10]
        finish = (t.get("finish") or "")[:10]
        if (start and start <= today_short and
                finish and finish > today_short and
                t.get("percent_complete", 0) == 0):
            days = (datetime.fromisoformat(today_short) -
                    datetime.fromisoformat(start)).days
            should_started.append({**t, "days_since_start": days})

    # --- Leaf tasks with no predecessors (outline_level >= 3) ---
    no_predecessors = [
        t for t in leaf
        if not t.get("predecessors") and t.get("outline_level", 0) >= 3
    ]

    # --- Parent-child consistency ---
    inconsistent = []
    for t in summary_tasks:
        prefix = (t.get("wbs") or "") + "."
        ol = t.get("outline_level", 0)
        direct_children = [
            c for c in tasks
            if (c.get("wbs") or "").startswith(prefix)
            and c.get("outline_level") == ol + 1
        ]
        if not direct_children:
            continue
        calc = sum(c.get("percent_complete", 0) for c in direct_children) / len(direct_children)
        reported = t.get("percent_complete", 0)
        diff = reported - calc
        if abs(diff) > CONSISTENCY_THRESHOLD:
            inconsistent.append({
                "wbs": t.get("wbs"),
                "name": t.get("name"),
                "reported_pct": reported,
                "calculated_pct": round(calc, 1),
                "diff": round(diff, 1),
                "child_count": len(direct_children),
                "direction": "over-reported" if diff > 0 else "under-reported",
            })
    inconsistent.sort(key=lambda x: -abs(x["diff"]))

    # --- Summary ---
    pred_count = len([t for t in leaf if t.get("predecessors")])
    leaf_count = len(leaf)

    return {
        "overdue": overdue,
        "should_started": should_started,
        "no_predecessors": no_predecessors,
        "inconsistent_parents": inconsistent,
        "summary": {
            "total_tasks": len(tasks),
            "leaf_tasks": leaf_count,
            "summary_tasks": len(summary_tasks),
            "overdue_count": len(overdue),
            "should_started_count": len(should_started),
            "predecessor_count": pred_count,
            "predecessor_pct": round(pred_count / leaf_count * 100, 1) if leaf_count else 0,
            "inconsistent_count": len(inconsistent),
            "milestones": len([t for t in tasks if t.get("milestone")]),
        },
    }


def build_issues_list(analysis, today=None):
    """Flatten analysis results into a single sorted issues list.

    Each issue: {severity, category, wbs, name, issue, detail}
    """
    today_short = (today or datetime.now().strftime("%Y-%m-%d"))[:10]
    issues = []

    for t in analysis["overdue"]:
        days = t["days_overdue"]
        sev = "CRITICAL" if days > OVERDUE_CRITICAL_DAYS else (
            "HIGH" if days > OVERDUE_HIGH_DAYS else "MEDIUM")
        issues.append({
            "severity": sev,
            "category": "Overdue",
            "wbs": t.get("wbs", ""),
            "name": t.get("name", ""),
            "issue": f"{days}d late",
            "detail": f"Due: {(t.get('finish') or '')[:10]}, {t.get('percent_complete', 0):.0f}% done",
        })

    for t in analysis["inconsistent_parents"]:
        sev = "HIGH" if abs(t["diff"]) > 20 else "MEDIUM"
        issues.append({
            "severity": sev,
            "category": "Consistency",
            "wbs": t["wbs"],
            "name": t["name"],
            "issue": f"Δ{t['diff']:+.0f}% ({t['direction']})",
            "detail": f"Reported: {t['reported_pct']:.0f}%, Actual: {t['calculated_pct']:.0f}%",
        })

    for t in analysis["should_started"]:
        days = t.get("days_since_start", 0)
        sev = "HIGH" if days > 14 else "MEDIUM"
        issues.append({
            "severity": sev,
            "category": "Not Started",
            "wbs": t.get("wbs", ""),
            "name": t.get("name", ""),
            "issue": f"{days}d past start",
            "detail": f"Start: {(t.get('start') or '')[:10]}, Finish: {(t.get('finish') or '')[:10]}",
        })

    # Sort: CRITICAL > HIGH > MEDIUM > LOW
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues.sort(key=lambda x: (sev_order.get(x["severity"], 9), x["category"], x["wbs"]))
    return issues
