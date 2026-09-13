---
name: search-docs
description: "Retrieves source-grounded answers from the git-library knowledge base by searching and reading official docs. Use when the user asks how a documented product, API, SDK, CLI, or MCP tool works; wants official docs, setup, configuration, migration, troubleshooting, latest features, or a library topic overview; or prefers cited documentation over a guessed answer. Typical asks include search docs, 查文档, 文档检索, API 文档, 官方文档, 怎么配, MCP 配置, migration guide, troubleshooting, 排错, 最新功能, and how-does-X-work questions about documented tools. Do not use for writing or reviewing application code that is not a docs or API question."
---

# Search Agentic Knowledge Base

## Goal
Route → retrieve → read source → answer. Minimal calls.

## Config
The producer-owned machine contract is [references/capability-contract.json](references/capability-contract.json); its pinned source, commit, hash, and license are in [references/capability-provenance.json](references/capability-provenance.json). Do not copy numeric policy into this file or infer it from prose. Read the contract when thresholds, budgets, or tool compatibility affect the task.

## Local entrypoint

Copying or symlinking the Skill does not install a command on PATH. Resolve
the directory of the **loaded SKILL.md** (not the task's working directory or
a guessed client location), then use the bundled entrypoint for every call:

```bash
SEARCH_DOCS_SKILL_DIR=/absolute/path/to/loaded/search-docs
search_docs() { bash "$SEARCH_DOCS_SKILL_DIR/scripts/search-docs" "$@"; }
search_docs doctor --offline
```

The examples below use this shell function. Across separate shell/tool calls,
define it again or call `bash "$SEARCH_DOCS_SKILL_DIR/scripts/search-docs"`
directly; functions and variables need not persist. Do not reinstall or edit
shell configuration just because the bare command is missing. Installation is
optional and requires authorization for its destination and CLI link; read
`scripts/install-search-docs --help` first. For caching calls, set
`GIT_LIBRARY_CACHE` to an approved runtime location if the default is out of scope.

## Search Response Schema
Each search result contains:
- `path`: Document path within library (e.g., "guides/setup.md")
- `title`: Document title (nullable)
- `summary`: Short document summary (nullable)
- `excerpt`: Matching text excerpt
- `raw_score`: BM25 raw score (nullable; lower = more relevant, e.g., -8.5)
- `display_score`: Normalized 0-100 score (nullable)
- `highlights`: Array of highlighted matching terms
- `library_id`: Library the result belongs to
- `last_updated`: ISO timestamp of last update (mode=recent only)

Wrapper payload includes:
- `total`: Total matches before pagination
- `limit`, `offset`: Pagination params
- `catalog`: Topic map or full catalog (per catalog_mode)
- `hint`: Human-readable summary of results

## Workflow: Navigate → Search → Probe → Fallback

### Navigate (preferred)
Already know the path? `search_docs read LIB_ID/PATH.md`

### Search (default)
1. Route to one primary library (explicit product/library mention wins).
2. Search inside that library:
```bash
search_docs search "QUERY" --library LIBRARY_ID --limit 8 --catalog-mode none
```
3. Check response confidence. Read top 1-3 docs before answering.

### Probe (ambiguity)
No clear library? Run cross-library probe:
```bash
search_docs search "QUERY" --limit 8
```
If results span multiple libraries with close scores under the contract's ambiguity gate:
- Interactive: ask only when the library choice would materially change the
  answer; otherwise read the best candidates and answer with the ambiguity
  disclosed.
- Non-interactive: return best + second candidate, mark uncertainty.

### Fallback (once)
Search confidence low? Browse manifest:
```bash
search_docs manifest LIBRARY_ID
```
Navigate topic map → read target doc. No repeated fallback loops.

## Freshness
Queries with "latest/new/recent/最新/刚发布":
```bash
search_docs libraries --fresh-for-query "QUERY"
```
If routing still weak, `search_docs libraries --refresh` then retry once.

## Explore Path
When user asks for structure/topics/coverage (not a concrete answer):
```bash
search_docs libraries
search_docs manifest LIBRARY_ID
```
Deliver: library positioning, topic distribution, recommended starting docs.

## Commands
```bash
search_docs health                                    # connectivity check
search_docs version                                   # bundled contract version
search_docs doctor --offline                          # local integrity check
search_docs libraries                                 # list all libraries
search_docs libraries --fresh-for-query "QUERY"        # freshness-aware list
search_docs search "Q" --library LIB --limit 8         # targeted search
search_docs search "Q" --limit 8                       # cross-library search
search_docs read LIB/PATH.md                           # read full document
search_docs manifest LIB                              # browse topic map
search_docs recent --days 7                           # recent updates
```

## Anti-Patterns
- Starting with cross-library search for every query — route first.
- Answering from snippets without reading source doc.
- Repeating fallback loops beyond one round.
- Treating static routing hints as stronger than live library metadata.
- Continuing after `doctor` reports contract or installation drift.
