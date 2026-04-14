# office-mpp

Microsoft Project 计划管理 Skill（原 `mpp-tracker` + `mpp-editor` 合并）。支持读取、分析、Gap 分析、Excel 导出、创建和编辑 `.mpp` / MSPDI `.xml` 项目计划文件。

**English**: A self-contained skill for reading, tracking, exporting, creating, and editing Microsoft Project plans (`.mpp` / MSPDI XML). Covers Plan vs Actual gap analysis, Gantt export to Excel, MSPDI authoring, and 8-rule structural validation.

## 功能

| 操作 | 说明 |
|------|------|
| **READ** | 解析 `.mpp` / `.xml`，输出摘要 / JSON / 任务表 / 里程碑 |
| **GAP** | Plan vs Actual 差异表（Board Meeting 格式），支持多文件合并 |
| **EXPORT** | 导出 Excel 审视表（Overview + Tasks + Overdue + Workstreams + Gantt）|
| **CREATE** | 从零或 JSON 规格创建新 MSPDI XML |
| **EDIT** | 更新任务 %、日期、名称；批量更新；删除；新增 |
| **VALIDATE** | 8 项结构校验（UID 唯一性、日期逻辑、百分比范围等）|

## 安装

```bash
# 复制整个 skill 目录到目标位置
cp -r .agents/skills/office-mpp /your/project/.agents/skills/office-mpp

# 检查环境依赖
bash /your/project/.agents/skills/office-mpp/scripts/env_check.sh
```

## 快速上手

```bash
SKILL_DIR=/your/project/.agents/skills/office-mpp

# 读取项目计划
python3 $SKILL_DIR/scripts/mpp_reader.py project.mpp

# GAP 分析（未来三周预测）
python3 $SKILL_DIR/scripts/mpp_plan_vs_actual.py project.mpp --weeks 3 --excel gap.xlsx

# 导出 Excel 审视表
python3 $SKILL_DIR/scripts/mpp_to_excel.py project.mpp --output review.xlsx

# 创建新计划
python3 $SKILL_DIR/scripts/mspdi_create.py --output plan.xml --title "My Project" --start 2026-04-15

# 编辑任务完成度
python3 $SKILL_DIR/scripts/mspdi_editor.py plan.xml --output plan-v2.xml \
    --update-task --uid 5 --percent-complete 90
```

## 目录结构

```
office-mpp/
├── SKILL.md              ← Skill 入口，task routing + 关键规则
├── README.md             ← 本文件
├── LICENSE               ← MIT
├── scripts/
│   ├── env_check.sh      ← 环境自检（支持 --json）
│   ├── mpp_reader.py     ← READ
│   ├── mpp_plan_vs_actual.py  ← GAP
│   ├── mpp_to_excel.py   ← EXPORT
│   ├── mspdi_create.py   ← CREATE
│   ├── mspdi_editor.py   ← EDIT
│   ├── mspdi_validate.py ← VALIDATE
│   ├── mpp_report.py     ← REPORT（维护）
│   ├── mpp_diff.py       ← DIFF（维护）
│   ├── mpp_converter.py  ← CONVERT（维护）
│   ├── mpp_analyze.py    ← ANALYZE（维护）
│   ├── schema.py         ← Task/Project 数据类契约
│   └── helpers/          ← 内部工具模块
├── references/
│   ├── gap.md            ← GAP 算法深度文档
│   ├── maintenance.md    ← 维护脚本指南
│   ├── examples.md       ← 项目化示例
│   └── ...               ← 各操作详细指南
├── templates/
│   └── minimal_mspdi/    ← 最小 MSPDI XML 模板
└── tests/                ← 测试套件
```

## 依赖

| 依赖 | 必需 | 用途 |
|------|------|------|
| `python3` | ✅ 必需 | 所有脚本 |
| `openpyxl` | ✅ 必需（EXPORT） | Excel 导出 |
| `java` ≥ 17 | ⚠️ .mpp 文件必需 | MPXJ 读取二进制 MPP |
| `mpxj` (Python) | ⚠️ .mpp 文件必需 | MPP 解析 |

`.xml` MSPDI 文件无需 Java / MPXJ，纯 Python 运行。

## 详细文档

参见 [SKILL.md](SKILL.md) 获取完整的 task routing、关键规则和命令示例。
