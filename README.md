# agent-skills

面向 AI Coding 高频场景的可复用 Agent Skills 仓库。每个
`skills/<name>/SKILL.md` 是一份可移植操作协议；部分 Skill 同时附带脚本、参考资料
或外部工具适配层。

## Skills

| Skill | 交付分类 | 能力 |
|---|---|---|
| `office-mpp` | bundled | Microsoft Project 读取、进度追踪、Gap 分析、Excel 导出与 MSPDI 编辑 |
| `search-docs` | adapter | 通过随附 CLI 访问 git-library，执行文档检索与问答 |
| `gemini-frontend` | adapter | 通过随附 helper 调用 Gemini CLI 完成前端设计、实现与视觉打磨 |
| `pdf-to-markdown` | protocol-only | 约定宿主项目中 PDF 文本抽取与 Markdown 还原流程 |
| `wechat-publish` | protocol-only | 约定宿主项目中微信公众号 dry-run、草稿创建与状态验证流程 |

分类含义：

- `bundled`：核心实现随 Skill 交付。
- `adapter`：适配层随 Skill 交付，运行时依赖外部 CLI 或 API。
- `protocol-only`：仓库只交付操作协议，所述命令必须由宿主项目提供。

机器可读清单见 [`skills/catalog.json`](skills/catalog.json)。

## 安装

克隆仓库后，将需要的完整 Skill 目录复制到客户端支持的位置：

```bash
git clone https://github.com/life-is-blue/agent-skills.git
cp -r agent-skills/skills/<name> <client-skill-directory>/
```

不同客户端对 Skill 目录、符号链接和 frontmatter 扩展的支持会变化。本仓库以
`SKILL.md` 协议和目录内相对路径为兼容边界；具体发现路径以所用客户端的当前文档
和本地 smoke test 为准。

复制后先阅读对应 `SKILL.md` 的依赖和预检步骤。`protocol-only` Skill 不能仅靠复制
本仓库目录直接运行。

## 仓库结构

```text
skills/<name>/
├── SKILL.md          # 必需：触发描述与操作协议
├── scripts/          # 可选：可执行实现或适配层
├── references/       # 可选：按需读取的领域资料
├── assets/           # 可选：输出所需资产
└── templates/        # 可选：可复用模板
```

治理规则和分类准入标准见 [`CONTRIBUTING.md`](CONTRIBUTING.md)，架构说明见
[`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 验证

```bash
python3 scripts/validate_repo.py
python3 -m pytest -q
```

相同检查会在 GitHub Actions 中阻断不合规变更。

## License

仓库默认使用 [MIT License](LICENSE)。Skill 目录中的独立许可证在其适用范围内优先。
