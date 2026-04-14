#!/usr/bin/env python3
"""Batch-convert MPP files to MSPDI XML and generate JSON summaries.

Usage:
    python3 mpp_converter.py <input.mpp> --output-dir <dir>               # single file
    python3 mpp_converter.py <dir_of_mpps> --output-dir <dir>             # batch directory
    python3 mpp_converter.py <dir> --output-dir <dir> --classify          # classify + convert
    python3 mpp_converter.py <dir> --output-dir <dir> --json-summary      # emit JSON summaries
"""

import sys
import os
import argparse
import json
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))


def _convert_single(mpp_path, output_dir, json_summary=False):
    """Convert a single MPP file to MSPDI XML and optionally JSON summary."""
    from helpers.jpype_bootstrap import get_reader, get_writer, get_file_format

    reader = get_reader()
    FF = get_file_format()

    basename = os.path.splitext(os.path.basename(mpp_path))[0]
    xml_path = os.path.join(output_dir, f"{basename}.xml")
    json_path = os.path.join(output_dir, f"{basename}.json")

    project = reader.read(mpp_path)

    # Write MSPDI XML
    writer = get_writer(FF.MSPDI)
    writer.write(project, xml_path)

    result = {
        "input": mpp_path,
        "xml_output": xml_path,
        "status": "ok",
    }

    if json_summary:
        props = project.getProjectProperties()
        tasks = project.getTasks()

        # Collect top-level WBS items (outline level 1)
        top_level = []
        for i in range(tasks.size()):
            t = tasks.get(i)
            ol = int(str(t.getOutlineLevel())) if t.getOutlineLevel() else 0
            if ol == 1:
                top_level.append({
                    "name": str(t.getName() or ""),
                    "percent_complete": float(str(t.getPercentageComplete())) if t.getPercentageComplete() else 0.0,
                })

        summary = {
            "file": os.path.basename(mpp_path),
            "title": str(props.getProjectTitle() or ""),
            "start": str(props.getStartDate() or ""),
            "finish": str(props.getFinishDate() or ""),
            "last_saved": str(props.getLastSaved() or ""),
            "task_count": tasks.size(),
            "resource_count": project.getResources().size(),
            "top_level_wbs": top_level,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        result["json_output"] = json_path
        result["summary"] = summary

    return result


def _classify(results):
    """Classify converted files by project group and version chain."""
    groups = {}

    for r in results:
        summary = r.get("summary", {})
        title = summary.get("title", "")
        filename = summary.get("file", "")

        # Determine group by title prefix
        if "GenAI" in title or "GenAI" in filename:
            group = "JUDO GenAI"
        elif "JUDO" in title or "JUDO" in filename:
            group = "JUDO Timeline"
        elif "XLS" in title or "XLS" in filename or "Big Data" in title:
            group = "XLS Big Data AIML"
        elif "master" in filename.lower():
            group = "Master Plan"
        else:
            group = "Other"

        if group not in groups:
            groups[group] = []

        groups[group].append({
            "file": filename,
            "title": title,
            "last_saved": summary.get("last_saved", ""),
            "task_count": summary.get("task_count", 0),
            "start": summary.get("start", ""),
            "finish": summary.get("finish", ""),
        })

    # Sort each group by last_saved descending to identify latest
    for group in groups:
        groups[group].sort(key=lambda x: x.get("last_saved", ""), reverse=True)

    classification = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(results),
        "groups": {},
    }

    for group, files in groups.items():
        classification["groups"][group] = {
            "count": len(files),
            "latest": files[0]["file"] if files else None,
            "files": files,
        }

    return classification


def main():
    parser = argparse.ArgumentParser(
        description="Batch-convert MPP files to MSPDI XML and JSON summaries"
    )
    parser.add_argument("input", help="Input MPP file or directory containing MPP files")
    parser.add_argument("--output-dir", required=True, help="Output directory for converted files")
    parser.add_argument("--json-summary", action="store_true", help="Also emit JSON summary per file")
    parser.add_argument("--classify", action="store_true", help="Classify files by project group")
    args = parser.parse_args()

    # Collect input files
    if os.path.isfile(args.input):
        mpp_files = [args.input]
    elif os.path.isdir(args.input):
        mpp_files = sorted(glob.glob(os.path.join(args.input, "*.mpp")))
    else:
        print(f"Error: Input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    if not mpp_files:
        print(f"Error: No MPP files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # If classifying, we need JSON summaries
    need_json = args.json_summary or args.classify

    print(f"Converting {len(mpp_files)} MPP file(s)...")
    results = []
    errors = []

    for i, mpp_path in enumerate(mpp_files, 1):
        basename = os.path.basename(mpp_path)
        try:
            result = _convert_single(mpp_path, args.output_dir, json_summary=need_json)
            results.append(result)
            print(f"  [{i}/{len(mpp_files)}] OK: {basename}")
        except Exception as e:
            errors.append({"file": basename, "error": str(e)})
            print(f"  [{i}/{len(mpp_files)}] FAIL: {basename} — {e}", file=sys.stderr)

    # Classification
    if args.classify and results:
        classification = _classify(results)
        class_path = os.path.join(args.output_dir, "classification.json")
        with open(class_path, "w", encoding="utf-8") as f:
            json.dump(classification, f, indent=2, ensure_ascii=False)
        print(f"\nClassification written to: {class_path}")

        # Print summary
        for group, info in classification["groups"].items():
            latest = info["latest"] or "(none)"
            print(f"  {group}: {info['count']} files, latest={latest}")

    # Summary
    print(f"\nDone: {len(results)} converted, {len(errors)} failed.")
    if errors:
        for e in errors:
            print(f"  Error: {e['file']}: {e['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
