---
name: search-docs
description: Search the git-library knowledge base for documentation. Use when user says "search docs", "find documentation", "look up", or asks questions about tools and libraries indexed in git-library.
---

# Search Knowledge Base

## Prerequisite

This skill requires an MCP server that provides:
- `list_libraries`
- `search_library`
- `read_document`
- `get_library_manifest`

Recommended hosted endpoint:
- `https://mcp.100100086.xyz/mcp` (git-library online MCP service)

## Current Libraries (git-library)

Always call `list_libraries` first to confirm real-time availability.

As of current `git-library` source config, the common library IDs are:
- `claude-code` — Claude Code official docs mirror
- `cnb-feedback` — CNB platform feedback and suggestions
- `codebuddy-docs` — CodeBuddy core documentation
- `gemini-cli` — Gemini CLI official docs
- `openai-codex` — OpenAI Codex official docs
- `bestblogs-ai-coding` — BestBlogs AI Coding featured articles (100)

## Instructions

1. **Pick the best library**: Check `list_libraries` or the tool descriptions to find the `library_id` whose description best matches the query topic.

2. **Search**: Call `search_library` with the chosen `library_id` and the user's query. Set `limit` to 5.

3. **Format results** as a concise list:
   - **Title** — one-line summary
   - Path: `library_id/path` (for `read_document`)
   - Excerpt: most relevant snippet

4. **If results are poor** (zero hits or irrelevant):
   - Try `search_library` without `library_id` (cross-library search).
   - Browse with `get_library_manifest` and suggest documents by title.

5. **Offer next steps**: Mention `read_document` to read any result in full.

## Usage Examples

### Example 1: Codex MCP setup

User asks: "How do I configure Codex MCP?"

1. Search official docs first:
   - `search_library(library_id="openai-codex", query="MCP setup codex", limit=5)`
2. If low quality, search across libraries:
   - `search_library(query="codex mcp add git-library", limit=5)`
3. Read best candidate:
   - `read_document(library_id="<picked-library>", path="<picked-path>")`

### Example 2: Claude Code workflow docs

User asks: "Find best practices for Claude Code agent workflow."

1. `search_library(library_id="claude-code", query="agent workflow best practices", limit=5)`
2. If needed, use `get_library_manifest(library_id="claude-code")` to browse titles.
3. Return top docs with path and short excerpt.

### Example 3: AI Coding practical case studies

User asks: "Find real-world AI coding cases from big teams."

1. `search_library(library_id="bestblogs-ai-coding", query="team practice case study", limit=5)`
2. If needed, cross-check:
   - `search_library(query="AI coding team practice Codex Cursor Claude Code", limit=8)`
