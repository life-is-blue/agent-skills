# Creating New MSPDI Project Plans

## When to Use

User asks to create a new project plan, timeline, or schedule from scratch.

## Workflow

1. **Plan structure** — Define tasks, outline levels, start dates, and durations
2. **Copy template** — Start from `templates/minimal_mspdi/project.xml`
3. **Populate XML** — Fill metadata, tasks, resources, assignments
4. **Validate** — Run `mspdi_validate.py` to check structure

## Script Usage

```bash
# Empty plan with title and start date
python3 scripts/mspdi_create.py --output plan.xml --title "My Project" --start 2026-04-15

# From JSON specification
python3 scripts/mspdi_create.py --output plan.xml --from-json plan.json

# From custom template
python3 scripts/mspdi_create.py --output plan.xml --from-template custom.xml --title "New"
```

## JSON Input Schema

```json
{
  "title": "Project Name",
  "start": "2026-04-15T08:00:00",
  "calendar": "Standard",
  "tasks": [
    {
      "name": "Phase 1 - Assessment",
      "outline_level": 1,
      "start": "2026-04-15",
      "duration_days": 20
    },
    {
      "name": "Requirement Analysis",
      "outline_level": 2,
      "start": "2026-04-15",
      "duration_days": 10
    },
    {
      "name": "Assessment Complete",
      "outline_level": 2,
      "milestone": true,
      "start": "2026-05-09"
    }
  ],
  "resources": [
    { "name": "Engineer A", "type": "work" },
    { "name": "PM", "type": "work" }
  ]
}
```

## Auto-Computed Fields

| Field | Logic |
|-------|-------|
| UID | Sequential starting from 1 (UID=0 reserved for project summary) |
| ID | Same as UID for new files |
| WBS | Generated from outline levels (e.g., 1, 1.1, 1.2, 2, 2.1) |
| Summary | Automatically detected: task is summary if next task has deeper outline level |
| Finish | Calculated from Start + Duration (skipping weekends) |
| Duration (PT format) | Converted from `duration_days` × 8 hours/day |

## Calendar

Default "Standard" calendar: Mon-Fri, 08:00-12:00 + 13:00-17:00 (8h/day, 40h/week).

## Common Patterns

**Milestone-only plan:**
```json
{
  "title": "Key Milestones",
  "start": "2026-04-15",
  "tasks": [
    { "name": "Phase 1 Complete", "outline_level": 1, "milestone": true, "start": "2026-05-30" },
    { "name": "Phase 2 Complete", "outline_level": 1, "milestone": true, "start": "2026-09-30" }
  ]
}
```

**Phased plan:**
```json
{
  "title": "Migration Plan",
  "start": "2026-04-15",
  "tasks": [
    { "name": "Phase 1 - AWS", "outline_level": 1, "start": "2026-04-15", "duration_days": 30 },
    { "name": "Assessment", "outline_level": 2, "start": "2026-04-15", "duration_days": 10 },
    { "name": "Migration", "outline_level": 2, "start": "2026-04-29", "duration_days": 15 },
    { "name": "Validation", "outline_level": 2, "start": "2026-05-20", "duration_days": 5 },
    { "name": "Phase 2 - GCP", "outline_level": 1, "start": "2026-05-27", "duration_days": 40 }
  ]
}
```

## Output

MSPDI XML file compatible with Microsoft Project import. Validate with `mspdi_validate.py` before delivery.
