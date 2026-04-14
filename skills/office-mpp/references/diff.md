# DIFF — Compare Two Plan Versions

Compare two MPP/MSPDI project plans and report differences.

## Quick Start

```bash
# Markdown diff to stdout
python3 scripts/mpp_diff.py old.xml new.xml

# Machine-readable JSON
python3 scripts/mpp_diff.py old.xml new.xml --json

# Write to file
python3 scripts/mpp_diff.py old.xml new.xml -o diff.md
```

## What It Compares

Tasks are matched by **UID** (stable across plan versions).

| Metric | Description |
|--------|-------------|
| Task count | Total / leaf task changes |
| Overdue trend | Overdue count old → new |
| Progress changes | Leaf tasks with ≥10% completion change |
| Added tasks | New UIDs in new file |
| Removed tasks | UIDs missing from new file |
| Date changes | Finish date shifts (sorted by magnitude) |

## Options

| Flag | Description |
|------|-------------|
| `--json` | Output JSON instead of markdown |
| `-o`, `--output` | Write to file instead of stdout |

## Dependencies

- `mpp_reader.py` — for parsing input (auto-imported)
- For `.mpp` files: MPXJ + JRE
- For `.xml` files: pure Python (ElementTree)
