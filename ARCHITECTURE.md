# ARCHITECTURE.md

## 目录结构

```
.
├── skills/                     # 技能定义（每个 Skill 一个目录）
│   ├── pdf-to-markdown/SKILL.md
│   └── wechat-publish/SKILL.md
├── docs/plans/                 # 任务计划
├── AGENTS.md                   # 智能体操作规范
└── README.md
```

## 设计理念

每个 Skill 是独立封装的原子能力，通过 `SKILL.md` 描述完整的使用协议、依赖和示例。仓库本身不包含运行时代码，仅作为技能定义的集合。
