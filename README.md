# agent-skills

一个开源、可复用的 Agent Skills 仓库，聚焦 AI Coding 高频场景。每个 Skill 独立封装，拿来即用。

## 收录技能

| 技能 | 说明 |
|------|------|
| `office-mpp` | Microsoft Project 项目计划读取、进度追踪、Gap 分析、Excel 导出、MSPDI 创建与编辑 |
| `search-docs` | 基于 git-library 的文档检索与问答，支持 API/配置/迁移/排障等场景 |
| `wechat-publish` | 微信公众号发布一条龙（排版、dry-run、图片上传、草稿创建/更新） |
| `pdf-to-markdown` | PDF 文本抽取并按启发式规则还原 Markdown 结构 |

每个技能的完整用法详见 `skills/<name>/SKILL.md`。

## 安装

先克隆仓库：

```bash
git clone https://github.com/life-is-blue/agent-skills.git
```

然后根据你使用的 AI 编码工具，将技能复制到对应目录。以安装 `pdf-to-markdown` 为例：

### Gemini CLI

```bash
mkdir -p .gemini/skills
cp -r agent-skills/skills/pdf-to-markdown .gemini/skills/
```

Gemini 自动扫描 `.gemini/skills/*/SKILL.md`，无需额外配置。

### Claude Code

```bash
mkdir -p .claude/skills
cp -r agent-skills/skills/pdf-to-markdown .claude/skills/
```

Claude Code 自动加载 `.claude/skills/` 下的技能。

### CodeBuddy Code

```bash
mkdir -p skills
cp -r agent-skills/skills/pdf-to-markdown skills/
```

CodeBuddy Code 自动发现项目根目录 `skills/*/SKILL.md`。

### OpenAI Codex CLI

Codex 使用 `AGENTS.md` 加载指令，不支持 skill 目录。将 SKILL.md 内容追加到项目的 `AGENTS.md`：

```bash
cat agent-skills/skills/pdf-to-markdown/SKILL.md >> AGENTS.md
```

### Cursor / Windsurf

Cursor 和 Windsurf 使用单文件规则（`.cursorrules` / `.windsurfrules`），不支持 skill 目录。将 SKILL.md 内容追加到规则文件：

```bash
# Cursor
cat agent-skills/skills/pdf-to-markdown/SKILL.md >> .cursorrules

# Windsurf
cat agent-skills/skills/pdf-to-markdown/SKILL.md >> .windsurfrules
```

### 速查表

| 工具 | 技能目录 | 安装方式 |
|------|---------|---------|
| Gemini CLI | `.gemini/skills/<name>/SKILL.md` | 复制目录 |
| Claude Code | `.claude/skills/<name>/SKILL.md` | 复制目录 |
| CodeBuddy Code | `skills/<name>/SKILL.md` | 复制目录 |
| Codex CLI | `AGENTS.md` | 追加内容 |
| Cursor | `.cursorrules` | 追加内容 |
| Windsurf | `.windsurfrules` | 追加内容 |

## 目录约定

```
skills/<skill-name>/SKILL.md    # 技能定义与使用协议
```
