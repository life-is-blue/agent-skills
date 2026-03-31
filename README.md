# agent-skills

一个开源、可复用的 Agent Skills 仓库，聚焦 AI Coding 高频场景：文档检索、微信排版与发布、PDF 转 Markdown。目标是提供“拿来即用”的最小实践模板，方便团队快速接入并二次扩展。

## 收录技能

- `search-docs`
  - 来源：`git-library/.claude/skills/search-docs/`
  - 作用：基于 `git-library` MCP 做文档检索（`claude-code`、`openai-codex`、`gemini-cli`、`codebuddy-docs`、`cnb-feedback`、`bestblogs-ai-coding`）
  - 推荐服务：`https://mcp.100100086.xyz/mcp`
- `wechat-format`
  - 来源：`formatter/.agents/skills/wechat-format/`
  - 作用：调用排版服务将 Markdown 转为公众号 HTML
  - 推荐服务：`https://md.izoa.fun`
- `wechat-publish`
  - 来源：`one-key-claude/.gemini/skills/wechat-publisher/`
  - 作用：公众号发布一条龙（dry-run、图片上传、草稿创建/更新、发布状态查询）
- `pdf-to-markdown`
  - 来源：`one-key-claude/.gemini/skills/pdf-to-markdown/`
  - 作用：PDF 文本抽取并按启发式规则还原 Markdown 结构

## 快速开始

### 1. 安装依赖

```bash
cd agent-skills
bun install
```

### 2. 接入文档检索 MCP（`search-docs`）

```bash
# Claude Code
claude mcp add --transport http git-library https://mcp.100100086.xyz/mcp

# Codex CLI（注意 --url）
codex mcp add git-library --url https://mcp.100100086.xyz/mcp
```

### 3. 微信排版（`wechat-format`）

```bash
curl -X POST https://md.izoa.fun/api/format \
  -H "Content-Type: application/json" \
  -d '{"markdown":"# Hello","themeId":"tencent-tech"}'
```

### 4. 微信发布（`wechat-publish`）

```bash
# 先预览（推荐）
bun run publish article.md --dry-run

# 再创建草稿
bun run publish article.md
```

### 5. PDF 转 Markdown（`pdf-to-markdown`）

```bash
bun run pdf2md ./docs/sample.pdf
```

## 运行依赖

| 技能 | 依赖 |
|---|---|
| `search-docs` | 可用的 MCP Server（需支持 `list_libraries`、`search_library`、`read_document`、`get_library_manifest`） |
| `wechat-format` | 可访问 `md.izoa.fun` 或兼容自建服务 |
| `wechat-publish` | `bun` + `gray-matter` + `marked` + `sharp`，并配置 `WECHAT_APPID` / `WECHAT_APPSECRET` |
| `pdf-to-markdown` | `bun` + `pdfjs-dist` |

## 目录约定

- `skills/<skill-name>/SKILL.md`：技能主说明
- `skills/<skill-name>/scripts/*`：技能脚本（可选）

---

## English (Brief)

`agent-skills` is a reusable open-source skill pack for AI coding workflows.  
It includes:
- `search-docs` (git-library MCP documentation search)
- `wechat-format` (Markdown -> WeChat HTML via API)
- `wechat-publish` (end-to-end WeChat draft/publish workflow)
- `pdf-to-markdown` (PDF text extraction to Markdown)

Quick setup:
1. `bun install`
2. Connect MCP:
   - `claude mcp add --transport http git-library https://mcp.100100086.xyz/mcp`
   - `codex mcp add git-library --url https://mcp.100100086.xyz/mcp`
