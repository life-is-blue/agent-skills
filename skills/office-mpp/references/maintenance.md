# Maintenance Scripts

These four scripts support operational workflows (version comparison, batch conversion, deep analysis, status reporting). They are not primary Skill operations and do not appear in the main SKILL.md task routing table.

---

## REPORT — Status / Todo Reports

Generate markdown status and todo reports from project data. Designed as fragments that drop into `00-project-mgmt/status.md` or `todo.md`.

```bash
# Status report: workstream progress + milestones + risk indicators
python3 SKILL_DIR/scripts/mpp_report.py project.mpp --status

# Todo report: active tasks + upcoming milestones + blockers
python3 SKILL_DIR/scripts/mpp_report.py project.mpp --todo

# Both reports in one pass
python3 SKILL_DIR/scripts/mpp_report.py project.mpp --status --todo

# Raw JSON for custom downstream formatting
python3 SKILL_DIR/scripts/mpp_report.py project.mpp --json
```

### Status Report Sections

- **Project Overview**: title, date range, total / leaf / overdue task counts
- **Workstream Progress**: OutlineLevel=1 items with %, start, finish, critical flag
- **Milestones**: status = `done` / `OVERDUE` / `AT RISK` / `on track`
  - OVERDUE: past finish date, not complete
  - AT RISK: within 7 days of finish and < 50% complete
- **Risk Indicators**: top-10 overdue tasks sorted by finish date; top-10 incomplete critical path tasks

### Todo Report Sections

- **Active Tasks**: non-complete leaf tasks sorted by finish date; priority = High (overdue or critical) / Medium (in progress) / Normal (not started)
- **Upcoming Milestones**: milestones due within next 30 days
- **Blockers / Overdue**: tasks past finish date with days-overdue count

---

## DIFF — Compare Two Plan Versions

Compare two MPP/MSPDI files and surface schedule changes.

```bash
# Markdown diff to stdout
python3 SKILL_DIR/scripts/mpp_diff.py old.xml new.xml

# Machine-readable JSON
python3 SKILL_DIR/scripts/mpp_diff.py old.xml new.xml --json

# Write to file
python3 SKILL_DIR/scripts/mpp_diff.py old.xml new.xml -o diff.md
```

Tasks are matched by **UID** (stable across plan versions). What is compared:

| Metric | Description |
|--------|-------------|
| Task count delta | Total / leaf task changes |
| Overdue trend | Overdue count old → new |
| Progress changes | Leaf tasks with ≥ 10% completion change |
| Added tasks | New UIDs in new file |
| Removed tasks | UIDs missing from new file |
| Date changes | Finish date shifts, sorted by magnitude |

**Typical use**: compare consecutive weekly snapshots of the same project plan to prepare a change-summary for SteerCo.

---

## CONVERT — Batch MPP → MSPDI XML

Convert one or more binary `.mpp` files to MSPDI XML (and optionally JSON summaries).

```bash
# Single file
python3 SKILL_DIR/scripts/mpp_converter.py file.mpp --output-dir ./output/

# Batch directory
python3 SKILL_DIR/scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/

# With per-file JSON summaries
python3 SKILL_DIR/scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/ --json-summary

# With project classification grouping
python3 SKILL_DIR/scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/ --classify
```

**Output per file**:
- `<basename>.xml` — full MSPDI XML
- `<basename>.json` — summary: title, dates, task count, top-level WBS (with `--json-summary`)
- `classification.json` — project group index (with `--classify`)

**Classification algorithm** groups files by title keyword into project families (e.g., "JUDO GenAI", "JUDO Timeline", "XLS Big Data AIML", "Master Plan"), sorted by `last_saved` descending.

**Requires**: Java ≥ 17 + `mpxj` Python package (MPXJ reads binary MPP format).

---

## ANALYZE — Deep Schedule Analysis

Provides detailed schedule metrics beyond the standard reader summary.

```bash
python3 SKILL_DIR/scripts/mpp_analyze.py project.xml --json
python3 SKILL_DIR/scripts/mpp_analyze.py project.xml --critical-chain
python3 SKILL_DIR/scripts/mpp_analyze.py project.xml --resource-loading
```

Typical output includes:
- Schedule Performance Index (SPI) and Cost Performance Index (CPI) approximations
- Longest path analysis (float per task)
- Resource loading by week / by resource
- Baseline vs current deviation summary

Supports both `.mpp` (MPXJ) and `.xml` MSPDI (pure Python).
