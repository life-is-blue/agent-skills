---
name: wechat-format
description: >
  Format Markdown into WeChat-ready HTML with beautiful themes.
  Use this skill when the user wants to convert Markdown or plain text
  into a styled article for WeChat Official Accounts (微信公众号).
  Supports 10 built-in themes, AI text polishing, and accent color customization.
---

# WeChat Article Formatter

You are an expert at formatting Markdown content into beautiful WeChat Official
Account articles using the Alchemy Formatter API.

## API Base URL

Production (official hosted service provided by our team): `https://md.izoa.fun`
Self-hosted: replace with your own deployment URL.

## Core Workflow

1. **Receive** user's Markdown or plain text
2. **Optionally polish** the text with AI (POST /api/ai)
3. **Format** the text into WeChat HTML (POST /api/format)
4. **Return** the HTML to the user — they paste it into WeChat MP Editor

## Endpoints

### POST /api/format — Markdown → WeChat HTML

The primary endpoint. Converts Markdown to HTML with inline CSS.

```bash
curl -X POST https://md.izoa.fun/api/format \
  -H "Content-Type: application/json" \
  -d '{
    "markdown": "# Hello World\n\n> Good typography lets words breathe.\n\nThis is a **demo** article.",
    "themeId": "wechat-story"
  }'
```

**Request Body (JSON):**

| Field       | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| markdown    | string | yes      | Markdown content to format               |
| themeId     | string | no       | Theme ID (default: `tencent-tech`)       |
| accentColor | string | no       | Hex color override, e.g. `#1a73e8`      |

**Response:**
```json
{
  "success": true,
  "html": "<section class=\"wx-content\">...</section>",
  "meta": { "theme": "wechat-story", "processedAt": "2025-01-01T00:00:00Z" }
}
```

The `html` field contains fully styled HTML with inline CSS. The user can paste
it directly into the WeChat MP Editor's code view.

### POST /api/ai — AI Text Processing

Polish, fix grammar, summarize, or auto-format text.

```bash
curl -X POST https://md.izoa.fun/api/ai \
  -H "Content-Type: application/json" \
  -d '{"text": "这是一段需要润色的文字", "action": "polish"}'
```

**Request Body (JSON):**

| Field  | Type   | Required | Description                                    |
|--------|--------|----------|------------------------------------------------|
| text   | string | yes      | Text to process                                |
| action | string | yes      | `polish` / `grammar` / `summarize` / `autoFormat` / `emphasize` |

**Actions explained:**
- `polish` — Rewrite for clarity and professionalism
- `grammar` — Fix grammatical errors only
- `summarize` — Generate a TL;DR summary
- `autoFormat` — Add Markdown headings, lists, emphasis
- `emphasize` — Highlight key arguments and bold key terms

> Requires OPENAI_API_KEY on the server. Returns 503 if not configured.

### GET /api/openapi — OpenAPI 3.0 Spec

Returns the machine-readable JSON spec for integration with ChatGPT Actions,
Coze, Dify, and other AI platforms.

## Available Themes

| ID               | Style                                |
|------------------|--------------------------------------|
| wechat-story     | Green, serif, literary               |
| tencent-tech     | Blue, clean, technical docs          |
| github           | Neutral, familiar developer style    |
| classic-song     | Warm, Song typeface, traditional     |
| history-book     | Red, Kai typeface, classical Chinese |
| google-clean     | Blue, Material Design inspired       |
| magazine-elegant | Purple, premium magazine feel        |
| zen-tea          | Earthy green, minimal and calm       |
| focus-dark       | Dark background, high contrast       |
| gemini-docs      | Google Gemini style, modern          |

## Guidelines

- **Always use `themeId`** when the user mentions a style preference. Match
  keywords: "技术" → `tencent-tech`, "文艺" → `wechat-story`, "暗色" → `focus-dark`.
- **Default to `tencent-tech`** if no preference is given — it works well for
  most content types.
- **Accent colors** can be overridden with `accentColor` for brand consistency.
  Example: a company using red branding → `"accentColor": "#E53935"`.
- **Return the HTML directly** — do not wrap it in code blocks. The user should
  be able to copy-paste the output.
- **For long articles**, consider using `/api/ai` with `action: "autoFormat"`
  first to add proper Markdown structure, then format with `/api/format`.

## MCP Integration

For deeper integration, connect via Streamable HTTP (no local Node.js required):

```bash
claude mcp add alchemy-formatter --transport http https://md.izoa.fun/api/mcp
```

This gives AI agents direct tool access to `wechat_format` and `polish_article` via the Model Context Protocol.
