# Monorepo TS Rewrite for ai-log-converter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保持现有 `wechat/publish/pdf2md` 能力稳定的前提下，把 `ai-log-converter` 从 Python 重写为 TypeScript，并完成 `apps/* + packages/*` monorepo 架构落地。

**Architecture:** 采用“两阶段迁移”：先在 `packages/ai-log-converter` 完成 TS 重写与语义一致 parity，再把根应用层迁移到 `apps/tooling-cli`，最终形成标准 monorepo。切换完成后不保留 Python 回滚开关，入口统一走 TS。

**Tech Stack:** Bun 1.x, TypeScript 5.x, Bun test, Zod（可选输入校验）, Biome。

## Locked Decisions (2026-03-31)

1. 采用并行迁移：先完成 TS 实现，再切主入口。
2. parity 目标为“语义一致”，不是字节级一致。
3. 切换后不保留 `LOG_CONVERTER_IMPL=python` 回滚开关。
4. 最终形态必须是 `apps/* + packages/*`。

## Semantic Parity Strategy (Recommended)

- 以“规范化消息模型”作为断言对象，而不是直接比较最终 Markdown 字符串。
- 断言维度：
  1. 角色序列一致（user/assistant/tool）
  2. block 类型一致（text/thought/tool_call/tool_result）
  3. 关键字段一致（tool name、input/output 语义）
  4. slop 值在可接受误差内（例如 `±0.001`）
- 对 Markdown/TXT 仅做“结构语义断言”（标题层级、tool block 是否存在），不做空白字符逐字节比对。

## Target Monorepo Layout

```text
.
├── package.json                     # root app + workspace root
├── apps/
│   └── tooling-cli/
│       ├── package.json
│       └── src/
│           ├── index.ts
│           └── cli/
│               ├── wechat.ts
│               ├── publish.ts
│               ├── pdf-to-md.ts
│               └── log-convert.ts
├── packages/
│   └── ai-log-converter/
│       ├── package.json
│       ├── tsconfig.json
│       ├── src/
│       │   ├── cli.ts
│       │   ├── index.ts
│       │   ├── types.ts
│       │   ├── clean.ts
│       │   ├── detect.ts
│       │   ├── source.ts
│       │   ├── mappers/
│       │   │   ├── claude.ts
│       │   │   ├── gemini.ts
│       │   │   ├── codebuddy.ts
│       │   │   └── codex.ts
│       │   └── render/
│       │       ├── md.ts
│       │       ├── txt.ts
│       │       └── jsonl.ts
│       └── tests/
│           ├── data/                # copied from ai-log-converter/tests/data
│           ├── detect.test.ts
│           ├── mapper.test.ts
│           ├── render.test.ts
│           └── parity.test.ts
└── skills/                          # behavior unchanged, only entry path updated
```

## Non-Goals (This Iteration)

- 不重构现有 `wechat/publish/pdf2md` 业务逻辑。
- 不引入额外运行时（如 Node-only runner）；统一使用 Bun。
- 不一次性删除 Python 版本，先并行验证再下线。

---

### Task 1: 建立 Workspace 骨架（不改业务）

**Files:**
- Modify: `package.json`
- Create: `packages/ai-log-converter/package.json`
- Create: `packages/ai-log-converter/tsconfig.json`
- Create: `packages/ai-log-converter/src/index.ts`

**Step 1: 写失败检查（workspace 未配置时应失败）**

```bash
bun install
bun --cwd packages/ai-log-converter run test
```

Expected: 命令不存在或目录未初始化失败。

**Step 2: 添加 workspace 与包清单（最小）**

`package.json` 增加：

```json
{
  "workspaces": ["packages/*"]
}
```

`packages/ai-log-converter/package.json`：

```json
{
  "name": "@agent-skills/ai-log-converter",
  "version": "0.1.0",
  "type": "module",
  "module": "src/index.ts",
  "scripts": {
    "test": "bun test",
    "typecheck": "bun x tsc --noEmit",
    "lint": "bun x @biomejs/biome check src tests"
  }
}
```

**Step 3: 验证骨架可运行**

```bash
bun install
bun --cwd packages/ai-log-converter run typecheck
```

Expected: 通过。

**Step 4: Commit**

```bash
git add package.json packages/ai-log-converter
git commit -m "chore: scaffold ai-log-converter workspace package"
```

---

### Task 2: 建立领域类型与清洗函数（TDD）

**Files:**
- Create: `packages/ai-log-converter/src/types.ts`
- Create: `packages/ai-log-converter/src/clean.ts`
- Create: `packages/ai-log-converter/tests/clean.test.ts`

**Step 1: 写失败测试（清洗和 slop 计算）**

```ts
import { describe, expect, it } from "bun:test";
import { cleanText, calculateSlop } from "../src/clean";

describe("clean", () => {
  it("removes caveat tags and collapses blank lines", () => {
    const input = "a<local-command-caveat>x</local-command-caveat>\n\n\n b";
    expect(cleanText(input)).toBe("a\n\n b");
  });

  it("calculates slop ratio", () => {
    expect(calculateSlop([{ type: "thought", text: "xx" }, { type: "text", text: "xx" }])).toBe(0.5);
  });
});
```

**Step 2: 运行测试确认失败**

```bash
bun --cwd packages/ai-log-converter run test clean.test.ts
```

Expected: FAIL with module/function not found。

**Step 3: 写最小实现**

实现 `cleanText`、`calculateSlop`，行为对齐 Python 版本。

**Step 4: 再跑测试**

```bash
bun --cwd packages/ai-log-converter run test clean.test.ts
```

Expected: PASS。

**Step 5: Commit**

```bash
git add packages/ai-log-converter/src/clean.ts packages/ai-log-converter/src/types.ts packages/ai-log-converter/tests/clean.test.ts
git commit -m "feat: add converter core clean and slop utilities"
```

---

### Task 3: 实现格式识别与 metadata 跳过（TDD）

**Files:**
- Create: `packages/ai-log-converter/src/detect.ts`
- Create: `packages/ai-log-converter/tests/detect.test.ts`

**Step 1: 写失败测试（覆盖 metadata 前缀场景）**

```ts
it("detects gemini after metadata lines", () => {
  const samples = [
    { type: "info", msg: "meta" },
    { type: "model", parts: [{ text: "hello" }] }
  ];
  expect(detectFormat(samples)).toBe("gemini");
});
```

**Step 2: 跑测试确认失败**

Run: `bun --cwd packages/ai-log-converter run test detect.test.ts`

Expected: FAIL。

**Step 3: 最小实现 `isMetadataEntry` + `detectFormat`**

与 Python 规则等价：跳过 `info/session_meta/...`、`response_item.reasoning`、`system/developer`。

**Step 4: 跑测试确认通过**

Run: `bun --cwd packages/ai-log-converter run test detect.test.ts`

Expected: PASS。

**Step 5: Commit**

```bash
git add packages/ai-log-converter/src/detect.ts packages/ai-log-converter/tests/detect.test.ts
git commit -m "feat: add robust format detection with metadata skipping"
```

---

### Task 4: 迁移四类 Mapper（Claude/Gemini/CodeBuddy/Codex）

**Files:**
- Create: `packages/ai-log-converter/src/mappers/claude.ts`
- Create: `packages/ai-log-converter/src/mappers/gemini.ts`
- Create: `packages/ai-log-converter/src/mappers/codebuddy.ts`
- Create: `packages/ai-log-converter/src/mappers/codex.ts`
- Create: `packages/ai-log-converter/src/mappers/index.ts`
- Create: `packages/ai-log-converter/tests/mapper.test.ts`

**Step 1: 写失败测试（每种格式至少 1 条 fixture）**

示例：

```ts
it("maps codex response_item message", () => {
  const out = [...mapCodex(entry)];
  expect(out[0].role).toBe("assistant");
});
```

**Step 2: 跑测试确认失败**

Run: `bun --cwd packages/ai-log-converter run test mapper.test.ts`

**Step 3: 最小实现 mapper**

要求：字段映射与 Python 当前行为一致；`tool_call/tool_result/thought/text` 类型对齐。

**Step 4: 跑测试确认通过**

Run: `bun --cwd packages/ai-log-converter run test mapper.test.ts`

**Step 5: Commit**

```bash
git add packages/ai-log-converter/src/mappers packages/ai-log-converter/tests/mapper.test.ts
git commit -m "feat: port claude gemini codebuddy codex mappers to ts"
```

---

### Task 5: 迁移渲染器（md/txt/jsonl）

**Files:**
- Create: `packages/ai-log-converter/src/render/md.ts`
- Create: `packages/ai-log-converter/src/render/txt.ts`
- Create: `packages/ai-log-converter/src/render/jsonl.ts`
- Create: `packages/ai-log-converter/tests/render.test.ts`

**Step 1: 写失败测试（md 工具调用块、txt role 前缀、jsonl 输出）**

**Step 2: 运行确认失败**

Run: `bun --cwd packages/ai-log-converter run test render.test.ts`

**Step 3: 实现渲染器**

- `md`: 标题、slop、text/thought/tool_call/tool_result block 对齐。
- `txt`: `[ROLE] text` 格式。
- `jsonl`: `JSON.stringify(msg) + "\n"`。

**Step 4: 运行确认通过**

Run: `bun --cwd packages/ai-log-converter run test render.test.ts`

**Step 5: Commit**

```bash
git add packages/ai-log-converter/src/render packages/ai-log-converter/tests/render.test.ts
git commit -m "feat: add md txt jsonl renderers"
```

---

### Task 6: 迁移 CLI 与流式读取

**Files:**
- Create: `packages/ai-log-converter/src/source.ts`
- Create: `packages/ai-log-converter/src/cli.ts`
- Modify: `packages/ai-log-converter/package.json` (bin/scripts)
- Create: `packages/ai-log-converter/tests/cli-smoke.test.ts`

**Step 1: 写失败测试（`--help`、stdin/stdout 模式）**

**Step 2: 运行失败确认**

Run: `bun --cwd packages/ai-log-converter run test cli-smoke.test.ts`

**Step 3: 实现 CLI**

行为要求：
- 参数兼容 Python：`-f/-t/-r/--no-thoughts [input] [output]`
- 成功路径 `stderr` 为空
- 未知格式/非法 JSON 返回非 0

**Step 4: 运行通过确认**

Run: `bun --cwd packages/ai-log-converter run test cli-smoke.test.ts`

**Step 5: Commit**

```bash
git add packages/ai-log-converter/src/source.ts packages/ai-log-converter/src/cli.ts packages/ai-log-converter/package.json packages/ai-log-converter/tests/cli-smoke.test.ts
git commit -m "feat: add streaming cli for ts converter"
```

---

### Task 7: Parity 测试（对齐现有 Python fixture）

**Files:**
- Create: `packages/ai-log-converter/tests/data/*` (copy from `ai-log-converter/tests/data/*`)
- Create: `packages/ai-log-converter/tests/parity.test.ts`

**Step 1: 写失败测试（4 格式 + role filter + metadata skip + stderr silent）**

**Step 2: 跑测试确认失败**

Run: `bun --cwd packages/ai-log-converter run test parity.test.ts`

**Step 3: 修正实现直至通过**

保证 TS 输出与当前 Python 关键语义一致（允许换行细节可控差异，需在断言中明示）。

**Step 4: 运行全包测试**

Run: `bun --cwd packages/ai-log-converter run test`
Expected: all pass。

**Step 5: Commit**

```bash
git add packages/ai-log-converter/tests
git commit -m "test: add parity coverage against python converter fixtures"
```

---

### Task 8: 接入主仓库统一入口（切换到 TS）

**Files:**
- Modify: `src/cli/log-convert.ts`
- Modify: `package.json`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`

**Step 1: 写失败测试（根脚本应调用 TS 包，而非 Python）**

可在根新增轻量 smoke：

```ts
it("root log-convert delegates to ts package", async () => {
  // spawn bun run log-convert --help and assert ts cli signature
});
```

**Step 2: 跑失败确认**

Run: `bun test src/**/*.test.ts`

**Step 3: 修改入口**

- 根命令调用 `@agent-skills/ai-log-converter` CLI。
- 文档更新为 TS 路径。
- 删除 Python 回滚开关配置路径，入口保持单实现。

**Step 4: 运行全量验证**

```bash
bun run typecheck
bun run lint
bun run test
bun run build
bun run log-convert --help
```

Expected: 全部通过。

**Step 5: Commit**

```bash
git add src/cli/log-convert.ts package.json README.md ARCHITECTURE.md
git commit -m "refactor: switch root log-convert entry to ts workspace package"
```

---

### Task 9: Python 实现退场策略（受控）

**Files:**
- Modify: `ai-log-converter/README.md`
- Create: `docs/references/log-converter-migration.md`

**Step 1: 写文档测试清单（人工验证）**

记录并执行：
- TS 与 Python 对同一输入输出差异对比
- 性能对比（大 JSONL）
- 下线前行为一致性验证

**Step 2: 执行并记录结果**

Run:

```bash
time bun run log-convert ai-log-converter/tests/data/codex_masked.jsonl -
time python3 ai-log-converter/ai-log-converter.py ai-log-converter/tests/data/codex_masked.jsonl -
```

**Step 3: 输出下线判定标准**

- Parity 测试全绿
- 核心样本性能不劣于 Python 明显阈值（例如 20%）

**Step 4: Commit**

```bash
git add ai-log-converter/README.md docs/references/log-converter-migration.md
git commit -m "docs: define python deprecation and ts migration policy"
```

---

### Task 10: 落地 `apps/* + packages/*` 最终目录

**Files:**
- Create: `apps/tooling-cli/package.json`
- Create: `apps/tooling-cli/tsconfig.json`
- Create: `apps/tooling-cli/src/index.ts`
- Move: `src/cli/*.ts` -> `apps/tooling-cli/src/cli/*.ts`
- Move: `src/core/*` -> `apps/tooling-cli/src/core/*`（仅应用层保留）
- Move: `src/schema/*` -> `apps/tooling-cli/src/schema/*`（应用专属 schema）
- Move: `src/services/*` -> `apps/tooling-cli/src/services/*`
- Modify: root `package.json` scripts（转发到 `bun --cwd apps/tooling-cli run ...`）
- Modify: `tsconfig.json`（root 作为 references 聚合）
- Modify: `README.md`, `ARCHITECTURE.md`

**Step 1: 写失败测试（旧路径脚本应失效）**

Run: `bun run wechat --help`
Expected: 失败（迁移前基线）。

**Step 2: 创建 app 包并迁移文件**

- 新建 `apps/tooling-cli` 包结构。
- 迁移 `src/` 下应用代码到 `apps/tooling-cli/src/`。
- 修正 import 为 app 内相对路径。

**Step 3: 更新根脚本转发**

示例：

```json
{
  "scripts": {
    "wechat": "bun --cwd apps/tooling-cli run wechat",
    "publish": "bun --cwd apps/tooling-cli run publish",
    "pdf2md": "bun --cwd apps/tooling-cli run pdf2md",
    "log-convert": "bun --cwd apps/tooling-cli run log-convert"
  }
}
```

**Step 4: 运行全量验证**

```bash
bun run typecheck
bun run lint
bun run test
bun run build
bun run wechat --help
bun run log-convert --help
```

Expected: 全部通过。

**Step 5: Commit**

```bash
git add apps/tooling-cli src package.json tsconfig.json README.md ARCHITECTURE.md
git commit -m "refactor: migrate root app to apps/tooling-cli monorepo layout"
```

---

## Rollout Strategy

1. 先并行（Python 基线对比 + TS 实现），入口先切 TS。
2. 通过语义一致 parity 与性能门槛后，直接移除 Python 入口。
3. 再完成 `apps/* + packages/*` 目录收敛。

## Acceptance Criteria

- `bun run log-convert` 默认走 TS。
- TS parity 测试覆盖现有 Python 用例并通过。
- 根仓库 `typecheck/lint/test/build` 全绿。
- 目录结构落地为 `apps/* + packages/*`。
- 文档中不存在指向 Python 脚本的主路径说明（仅迁移说明中保留）。

Plan complete and saved to `docs/plans/2026-03-31-monorepo-ts-log-converter.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration

2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
