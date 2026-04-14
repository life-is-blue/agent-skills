# Batch Conversion of MPP Files

## When to Use

User has one or more .mpp files and wants to convert them to MSPDI XML (and optionally JSON summaries).

## Workflow

1. **Scan** — Find all .mpp files in input path
2. **Convert** — Read each MPP with MPXJ, write MSPDI XML
3. **Summarize** — Optionally generate JSON summary per file
4. **Classify** — Optionally group files by project and version chain

## Script Usage

```bash
# Single file
python3 scripts/mpp_converter.py file.mpp --output-dir ./output/

# Batch directory
python3 scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/

# With JSON summaries
python3 scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/ --json-summary

# With classification
python3 scripts/mpp_converter.py ./mpp-files/ --output-dir ./mpp-files/ --classify
```

## Output Per File

| Output | Filename | Content |
|--------|----------|---------|
| MSPDI XML | `<basename>.xml` | Full project data in MS Project XML format |
| JSON summary | `<basename>.json` | Title, dates, task count, top-level WBS |

## Classification Algorithm

When `--classify` is used:

1. Read each MPP's metadata (title, dates, task count)
2. Group by title keyword:
   - "JUDO GenAI" → JUDO GenAI group
   - "JUDO" → JUDO Timeline group
   - "XLS", "Big Data" → XLS Big Data AIML group
   - "master" → Master Plan group
3. Sort each group by `last_saved` descending
4. Output `classification.json` with groups and latest file per group

## Classification Output

```json
{
  "generated_at": "2026-04-11T...",
  "total_files": 16,
  "groups": {
    "JUDO Timeline": {
      "count": 7,
      "latest": "JUDO Timeline 0410(aws-gcp-classAI).mpp",
      "files": [...]
    }
  }
}
```

## Naming Conventions

Converted files are placed alongside originals:
```
mpp/
  JUDO Timeline 0410.mpp          # original (binary)
  JUDO Timeline 0410.xml          # converted XML
  JUDO Timeline 0410.json         # summary JSON
  classification.json             # group index
```

## Notes

- Conversion requires JVM (MPXJ reads binary MPP format)
- Existing XML files in the output directory are overwritten
- Failed conversions are reported to stderr but don't stop batch processing
