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
