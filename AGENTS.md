# AGENTS.md - 智能体操作宪法

> "Codex 看不到的东西就不存在。" —— 像素级模仿 OpenAI 实践。

## 核心原则

1. **仓库即真相 (Repository as Source of Truth)**: 
   - 禁止在仓库外存储决策。所有的 Slack 讨论、设计思路、架构变更必须转化为 `docs/` 下的 Markdown。
   - 智能体每次任务前必须运行 `git status` 和阅读最近的 `docs/plans`。

2. **强类型契约 (Strict Type Contracts)**:
   - 所有的业务数据模型必须定义在 `src/schema/` 中。
   - 禁止使用 `any`。所有外部输入必须通过 Zod 验证。

3. **单向依赖流 (Unidirectional Dependency)**:
   - 遵循分层：`Schema -> Core (Pure) -> Services -> CLI/Runtime`。
   - 禁止反向依赖（例如 Core 逻辑禁止引用 CLI 代码）。

4. **Hermeticity (封闭性)**:
   - 优先使用 Bun 内置 API (`Bun.file`, `Bun.password`, `Bun.sqlite`)。
   - 引入第三方库需在 `ARCHITECTURE.md` 中记录理由。

## 智能体工作流 (像素级模仿)

1. **Research**: 检查 `docs/plans/active/` 确认当前任务情境。
2. **Plan**: 在 `docs/plans/active/` 创建新的任务计划 Markdown。
3. **Act**: 执行代码变更，确保 `bun test` 和 `bun run lint` 通过。
4. **Validate**: 运行自动化测试，并根据需要更新文档。
5. **Garbage Collection**: 任务完成后，清理临时日志，将计划移至 `docs/plans/completed/`。

---
*Version: 0.1.0*
