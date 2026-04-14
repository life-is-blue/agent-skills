# ARCHITECTURE.md

## 目录结构

```
.
├── skills/                     # 技能定义（每个 Skill 一个目录）
│   ├── office-mpp/             # Microsoft Project 读取/追踪/导出/创建/编辑
│   │   ├── SKILL.md
│   │   ├── scripts/            # Python 脚本 + helpers
│   │   ├── references/         # 操作指南
│   │   ├── templates/          # MSPDI 模板
│   │   └── tests/              # 测试套件
│   ├── pdf-to-markdown/SKILL.md
│   └── wechat-publish/SKILL.md
├── docs/plans/                 # 任务计划
├── AGENTS.md                   # 智能体操作规范
└── README.md
```

## 设计理念

每个 Skill 是独立封装的原子能力，通过 `SKILL.md` 描述完整的使用协议、依赖和示例。仓库本身不包含运行时代码，仅作为技能定义的集合。
