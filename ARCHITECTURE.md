# ARCHITECTURE.md - 技能仓库架构

## 设计理念

每个 Skill 是独立封装的原子能力，通过 `skills/<name>/SKILL.md` 描述用法和协议。

## 目录结构

```
.
├── skills/                     # 技能定义（SKILL.md）
│   ├── pdf-to-markdown/
│   └── wechat-publish/
├── packages/                   # 可复用执行器（Bun Workspace）
│   └── ai-log-converter/
├── docs/plans/                 # 任务计划
│   ├── active/
│   └── completed/
└── AGENTS.md                   # 智能体操作规范
```

## 工具链

- **Runtime**: Bun 1.x
- **Linter/Formatter**: Biome
- **Test Runner**: Bun Test

## Packages

`packages/` 下的包通过 Bun Workspace 管理，可被技能脚本引用。

- `ai-log-converter` — AI 对话日志格式识别与清洗
