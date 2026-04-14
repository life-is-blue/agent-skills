# agent-skills

一个开源、可复用的 Agent Skills 仓库，聚焦 AI Coding 高频场景。每个 Skill 独立封装，拿来即用。

## 收录技能

| 技能 | 说明 |
|------|------|
| `wechat-publish` | 微信公众号发布一条龙（排版、dry-run、图片上传、草稿创建/更新） |
| `pdf-to-markdown` | PDF 文本抽取并按启发式规则还原 Markdown 结构 |

## 快速开始

```bash
bun install
```

技能说明详见各自的 `skills/<name>/SKILL.md`。

## 目录约定

```
skills/<skill-name>/SKILL.md    # 技能定义与使用协议
packages/<name>/                # 可复用执行器（Bun Workspace）
docs/plans/active/              # 进行中的任务计划
docs/plans/completed/           # 已完成的任务计划
```
