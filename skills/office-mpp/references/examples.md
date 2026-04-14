# Projectized Examples

Real-world usage patterns from the XLSmart data migration project.

---

## Example 1: XLSmart Multi-MPP GAP Analysis (Board Meeting)

The XLSmart project maintains two active MPP files — one for "Big Data Migration" (GCP/AWS/AB Initio → Tencent Cloud) and one for "GenAI Platform". The Board Meeting slides require a merged Plan vs Actual table.

```bash
SKILL_DIR=.agents/skills/office-mpp
MPP_DIR=xlsmart-project/99-raw-assets/20260411-mpp-files/

# Step 1: Convert .mpp → MSPDI XML (needs Java + MPXJ)
python3 $SKILL_DIR/scripts/mpp_converter.py $MPP_DIR --output-dir $MPP_DIR --classify

# Step 2: Inspect classification
cat $MPP_DIR/classification.json

# Step 3: Merge both plans into one gap table (3-week forecast)
python3 $SKILL_DIR/scripts/mpp_plan_vs_actual.py \
    "$MPP_DIR/JUDO Timeline 0410.xml" \
    "$MPP_DIR/JUDO GenAI 0410.xml" \
    --weeks 3 --excel gap-board-meeting.xlsx

# Step 4: Verify — check source column in JSON output
python3 $SKILL_DIR/scripts/mpp_plan_vs_actual.py \
    "$MPP_DIR/JUDO Timeline 0410.xml" \
    "$MPP_DIR/JUDO GenAI 0410.xml" \
    --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ws in data['workstreams']:
    print(f\"{ws['name']}: gap={ws['gap_pct']:.1f}% source={ws['gap_pct_source']}\")
"
```

**Expected output**: workstreams with `source: "mpp"` use PM-approved values from Number3/Number4; `source: "computed"` flags computationally derived values for PM review.

---

## Example 2: Big Data Migration — Weekly Status Report

Every Monday, extract updated status report fragments for the weekly sync meeting.

```bash
SKILL_DIR=.agents/skills/office-mpp
MPP_FILE=xlsmart-project/99-raw-assets/20260411-mpp-files/JUDO-Timeline-0410.xml

# Generate both status + todo in one pass
python3 $SKILL_DIR/scripts/mpp_report.py $MPP_FILE --status --todo \
    > xlsmart-project/03-meeting-notes/weekly-status-$(date +%Y%m%d).md

# Check overdue tasks
python3 $SKILL_DIR/scripts/mpp_reader.py $MPP_FILE --overdue

# Check milestone status
python3 $SKILL_DIR/scripts/mpp_reader.py $MPP_FILE --milestones
```

---

## Example 3: Version Diff After PM Updates

PM updates the plan on Monday and drops the new file. Compare against last week's snapshot.

```bash
SKILL_DIR=.agents/skills/office-mpp

python3 $SKILL_DIR/scripts/mpp_diff.py \
    xlsmart-project/99-raw-assets/20260404-mpp-files/JUDO-Timeline-0404.xml \
    xlsmart-project/99-raw-assets/20260411-mpp-files/JUDO-Timeline-0410.xml \
    -o xlsmart-project/03-meeting-notes/plan-diff-20260411.md

cat xlsmart-project/03-meeting-notes/plan-diff-20260411.md
```

---

## Example 4: Create New GenAI Sub-Project Plan

New "GenAI Platform" workstream added. Create initial plan from JSON spec.

```bash
SKILL_DIR=.agents/skills/office-mpp

# Define spec
cat > /tmp/genai-plan.json << 'JSON'
{
  "title": "GenAI Platform 2026",
  "start": "2026-05-01",
  "tasks": [
    { "name": "Phase 1 - Foundation", "outline_level": 1, "start": "2026-05-01", "duration_days": 30 },
    { "name": "LLM API Integration", "outline_level": 2, "start": "2026-05-01", "duration_days": 15 },
    { "name": "Vector DB Setup", "outline_level": 2, "start": "2026-05-20", "duration_days": 10 },
    { "name": "Phase 1 Complete", "outline_level": 2, "milestone": true, "start": "2026-05-30" },
    { "name": "Phase 2 - Productionize", "outline_level": 1, "start": "2026-06-02", "duration_days": 45 }
  ]
}
JSON

python3 $SKILL_DIR/scripts/mspdi_create.py \
    --output xlsmart-project/99-raw-assets/20260501-mpp-files/genai-platform.xml \
    --from-json /tmp/genai-plan.json

# Validate immediately
python3 $SKILL_DIR/scripts/mspdi_validate.py \
    xlsmart-project/99-raw-assets/20260501-mpp-files/genai-platform.xml
```

---

## Example 5: Batch Update Task Completion

After sprint review, batch-update completion % for multiple tasks.

```bash
SKILL_DIR=.agents/skills/office-mpp

cat > /tmp/updates.json << 'JSON'
[
  { "uid": 12, "percent_complete": 100, "actual_finish": "2026-04-10T17:00:00" },
  { "uid": 15, "percent_complete": 75 },
  { "uid": 18, "percent_complete": 30, "notes": "Delayed by API dependency" },
  { "name": "LLM API Integration", "percent_complete": 90 }
]
JSON

python3 $SKILL_DIR/scripts/mspdi_editor.py \
    current-plan.xml \
    --output updated-plan.xml \
    --batch-update /tmp/updates.json

# Validate and export
python3 $SKILL_DIR/scripts/mspdi_validate.py updated-plan.xml
python3 $SKILL_DIR/scripts/mpp_to_excel.py updated-plan.xml --output updated-review.xlsx
```

---

## Example 6: Excel Review Spreadsheet for Client

Before a client review meeting, export a polished Excel spreadsheet.

```bash
SKILL_DIR=.agents/skills/office-mpp

python3 $SKILL_DIR/scripts/mpp_to_excel.py \
    xlsmart-project/99-raw-assets/20260411-mpp-files/JUDO-Timeline-0410.xml \
    --output xlsmart-project/01-customer-deliverables/project-review-20260414.xlsx

# Preview what was generated
python3 $SKILL_DIR/scripts/mpp_reader.py \
    xlsmart-project/99-raw-assets/20260411-mpp-files/JUDO-Timeline-0410.xml \
    --summary-level 2
```

The exported file contains: Overview sheet, All Tasks sheet (with indentation + color coding), Overdue sheet (red-highlighted), Workstreams sheet, and a cell-fill Gantt chart tab.
