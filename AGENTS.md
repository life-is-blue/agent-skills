# AGENTS.md - 智能体操作规范

## 核心原则

1. **仓库即真相**: 所有决策记录在仓库内，不依赖外部讨论。
2. **Skill 独立封装**: 每个技能通过 `skills/<name>/SKILL.md` 完整描述用法和协议。

## 智能体工作流

1. **Research**: 阅读相关 `skills/` 目录确认任务情境。
2. **Plan**: 在 `docs/plans/` 创建任务计划。
3. **Act**: 执行变更。
4. **Validate**: 验证结果，更新文档。

## 避坑表

| 坑 | 解法 |
|---|---|
| 装 skill 到 `<project>/.claude/skills/` 后 Claude Code 报 `Unknown skill: <name>`，但脚本直接 `bash` 调能跑 | 必须在 `.claude/skills/` 所在目录启动 Claude Code（`cd <project> && claude`），不是在父目录——Claude 只扫当前 workspace 的 skill 目录。Linux 实测软链在正确 CWD 下可用；macOS 上软链有已知 bug [#14836](https://github.com/anthropics/claude-code/issues/14836)，跨平台保险用 `cp -r` |
| 子进程报 `rg: command not found`，但 Claude Code 终端里 `rg` 能用 | `rg` 在 Claude Code 终端里是 bash function 不是真二进制，子进程拿不到。装系统包：`sudo dnf install -y ripgrep`（Debian 系 `apt`、macOS `brew`） |
| 外部 CLI 的 flag 名或 JSON 字段名，WebFetch 回的文档描述对不上实际行为 | 以本地 `<cmd> --help` + 最小 smoke 调用为准。例：Gemini 的流式输出实际是 `-o stream-json`，但第三方文档站给的是 `streaming-json`；事件字段也只有实跑一次才知道真实 shape |

新增坑：现象 + 解法两列即可，必要时附一个查证链接。

---
*Version: 0.4.0*
