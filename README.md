# agent-skills

中文说明：这是一个可直接复用的开源技能仓库，聚焦 AI Coding 场景下的文档检索、微信排版/发布、PDF 转 Markdown 等高频流程。仓库内技能可独立使用，也可按需组合到你的 MCP/Agent 工作流中，默认优先提供最小依赖、可落地、可二次改造的实践模板。

A standalone, open-source skill pack extracted from local production repositories.

Minimal, practical, and reusable.

## Included Skills

- `search-docs`
  - Source: `git-library/.claude/skills/search-docs/`
  - Purpose: Query docs from git-library MCP knowledge libraries (`claude-code`, `openai-codex`, `gemini-cli`, `codebuddy-docs`, `cnb-feedback`, `bestblogs-ai-coding`).
  - Hosted MCP service: `https://mcp.100100086.xyz/mcp`

- `wechat-format`
  - Source: `formatter/.agents/skills/wechat-format/`
  - Purpose: Format Markdown to WeChat-ready HTML via API.
  - Hosted formatting service: `https://md.izoa.fun`

- `wechat-publish`
  - Source: `one-key-claude/.gemini/skills/wechat-publisher/`
  - Purpose: End-to-end WeChat publishing workflow (dry-run preview, image upload, draft create/update, submit/status).

- `pdf-to-markdown`
  - Source: `one-key-claude/.gemini/skills/pdf-to-markdown/`
  - Purpose: Convert PDF text to Markdown with heuristic layout reconstruction.

## Runtime Dependencies

| Skill | What you need |
|---|---|
| `search-docs` | A connected MCP server exposing `list_libraries`, `search_library`, `read_document`, `get_library_manifest` (recommended: `https://mcp.100100086.xyz/mcp`) |
| `wechat-format` | Network access to `https://md.izoa.fun` (or self-hosted compatible API) |
| `wechat-publish` | `bun` runtime + deps `gray-matter`, `marked`, `sharp`; `.env` with `WECHAT_APPID`, `WECHAT_APPSECRET` |
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

### 4) Publish to WeChat draft box (for `wechat-publish`)

```bash
# Preview first
bun skills/wechat-publish/scripts/publish.ts article.md --dry-run

# Create draft
bun skills/wechat-publish/scripts/publish.ts article.md
```

## Layout

- `skills/<skill-name>/SKILL.md`
- Optional scripts are included under each skill folder.

## Notes

These skills are copied as-is from source projects to keep extraction minimal and non-invasive.
