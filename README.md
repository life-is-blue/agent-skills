# agent-skills

A standalone, open-source skill pack extracted from local production repositories.

Minimal, practical, and reusable.

## Included Skills

- `search-docs`
  - Source: `git-library/.claude/skills/search-docs/`
  - Purpose: Query docs from MCP knowledge libraries.
  - Hosted MCP service: `https://mcp.100100086.xyz/mcp`

- `wechat-format`
  - Source: `formatter/.agents/skills/wechat-format/`
  - Purpose: Format Markdown to WeChat-ready HTML via API.
  - Hosted formatting service: `https://md.izoa.fun`

- `pdf-to-markdown`
  - Source: `one-key-claude/.gemini/skills/pdf-to-markdown/`
  - Purpose: Convert PDF text to Markdown with heuristic layout reconstruction.

## Runtime Dependencies

| Skill | What you need |
|---|---|
| `search-docs` | A connected MCP server exposing `list_libraries`, `search_library`, `read_document`, `get_library_manifest` (recommended: `https://mcp.100100086.xyz/mcp`) |
| `wechat-format` | Network access to `https://md.izoa.fun` (or self-hosted compatible API) |
| `pdf-to-markdown` | `bun` runtime + local dependency `pdfjs-dist` |

## Quick Start

### 1) Install local dependency (for `pdf-to-markdown`)

```bash
cd agent-skills
bun install
```

### 2) Connect hosted MCP service (for `search-docs`)

```bash
# Claude Code
claude mcp add --transport http git-library https://mcp.100100086.xyz/mcp

# Codex CLI
codex mcp add git-library https://mcp.100100086.xyz/mcp
```

### 3) Use hosted formatting API (for `wechat-format`)

```bash
curl -X POST https://md.izoa.fun/api/format \
  -H "Content-Type: application/json" \
  -d '{"markdown":"# Hello","themeId":"tencent-tech"}'
```

## Layout

- `skills/<skill-name>/SKILL.md`
- Optional scripts are included under each skill folder.

## Notes

These skills are copied as-is from source projects to keep extraction minimal and non-invasive.
