# Architecture

## 设计边界

仓库的基本单元是 `skills/<name>/SKILL.md`。它负责描述触发条件与操作协议；脚本、
参考资料、资产和模板都是按需附加资源。仓库既包含纯协议，也包含实际运行代码，
不能假设所有 Skill 具有相同交付形态。

根级 `skills/catalog.json` 记录交付分类，避免在不同客户端共同读取的 frontmatter 中
加入私有治理字段：

- `bundled`：核心实现位于 Skill 目录。
- `adapter`：Skill 目录提供外部 CLI/API 的适配层。
- `protocol-only`：仅定义宿主项目应遵循的执行协议。

## 目录职责

```text
.
├── skills/
│   ├── catalog.json           # Skill 名单与交付分类
│   └── <name>/
│       ├── SKILL.md           # 必需，可移植协议
│       ├── scripts/           # 可选，确定性实现或适配器
│       ├── references/        # 可选，按需加载的领域资料
│       ├── assets/            # 可选，输出资产
│       └── templates/         # 可选，可复用模板
├── scripts/validate_repo.py   # 仓库统一静态校验
├── docs/plans/                # 任务决策与验收记录
├── CONTRIBUTING.md            # 准入与合并规则
└── AGENTS.md                  # 智能体操作规范
```

## 质量门槛

`scripts/validate_repo.py` 校验目录与 catalog 一致性、frontmatter 可移植性、命名、
本地链接、资源引用和脚本语法。领域测试独立运行；当前 `office-mpp` 使用 pytest。
GitHub Actions 从仓库根目录执行两类检查，不调用需要密钥或会修改外部状态的服务。

外部客户端的 Skill 扫描规则不属于此架构的稳定接口。安装文档只承诺完整目录可复制，
客户端兼容性必须以其当前文档和最小 smoke 调用验证。
