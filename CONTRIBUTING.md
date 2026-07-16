# Contributing

本仓库以 `skills/<name>/SKILL.md` 为可移植协议。新增或修改 Skill 时，先在
`docs/plans/` 记录目标和验收标准，再执行变更并运行统一校验。

## Skill 准入标准

每个 Skill 必须满足：

- 目录名使用小写字母、数字和连字符，且与 frontmatter 的 `name` 完全一致。
- `SKILL.md` frontmatter 只包含 `name` 和 `description`；`description` 同时说明
  能力与触发场景。
- 正文使用指令式表达，保留核心流程；细节放入一级 `references/`，避免重复。
- 只创建实际需要的 `scripts/`、`references/`、`assets/` 和 `templates/`。
- 命令、依赖、输入输出、副作用和失败处理必须明确；不得声称仓库未提供的文件
  可以直接运行。
- 在 `skills/catalog.json` 中登记且只登记一次。

## 交付分类

| 分类 | 定义 | 最低要求 |
|---|---|---|
| `bundled` | 核心实现随 Skill 一起交付 | 脚本或资产存在，关键路径有可重复验证 |
| `adapter` | 仓库交付适配层，实际能力依赖外部 CLI/API | 适配脚本存在，依赖检查与失败提示明确 |
| `protocol-only` | 只交付供宿主项目执行的操作协议 | 明确标注不含实现，并在执行前检查宿主命令/文件 |

分类描述交付形态，不代表成熟度。外部客户端的扫描目录和安装方式不属于本仓库
兼容性承诺；默认安装方式是复制完整 Skill 目录到客户端支持的位置。

## 目录与文档

`SKILL.md` 是唯一必需文件。不要在 Skill 内新增 README、安装指南、变更日志或
审计过程文档；面向贡献者的信息放在根文档，领域细节放在 `references/`。已有
遗留文件可以在独立变更中迁移，新增内容不得扩大遗留范围。

本地 Markdown 链接必须使用相对路径并指向现存文件。超过约 500 行的
`SKILL.md` 应拆分；超过约 100 行的 reference 应提供目录或清晰的段落导航。

## 验证与合并

从仓库根目录运行：

```bash
python3 scripts/validate_repo.py
python3 -m pytest -q
```

第一个命令检查目录清单、frontmatter、命名、局部链接、脚本语法和文档中引用的
仓库路径。GitHub Actions 执行相同检查；失败时不得合并。

涉及外部 CLI 或 API 的变更，除静态校验外还应记录一次最小 smoke 结果。不得在
CI 中调用需要密钥、产生费用或修改外部状态的接口。

## 当前已知测试债

`office-mpp` 的测试文件仍包含 placeholder 和待实现用例。现有测试必须稳定通过，
但 placeholder 数量不得增加；补齐业务覆盖应作为独立任务推进。
