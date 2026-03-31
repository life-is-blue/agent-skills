# ARCHITECTURE.md - 领域分层设计

## 架构模型 (Google Style + OpenAI Layering)

本项目采用严格的单向依赖架构。每一层只能“向前”依赖。

### 1. Schema 层 (`src/schema/`)
- **定义**: 业务实体和数据契约。
- **工具**: Zod。
- **规则**: 禁止包含任何逻辑。仅定义数据结构。

### 2. Core 层 (`src/core/`)
- **定义**: 纯逻辑和算法（例如日志转换算法）。
- **规则**: 无副作用。禁止进行网络、文件 I/O 操作。

### 3. Services 层 (`src/services/`)
- **定义**: 业务流编排。
- **规则**: 允许调用 Core 和进行 I/O 操作。它是连接 Schema 和 Runtime 的桥梁。

### 4. Entry 层 (`src/cli/` 或 `src/index.ts`)
- **定义**: 应用程序入口。
- **规则**: 极薄的包装层。处理参数解析、环境初始化。

## 工具链选择 (Bun Native)
- **Runtime**: Bun 1.x
- **Linter/Formatter**: Biome (Google Style compliant)
- **Test Runner**: Bun Test
- **Database**: Bun SQLite (if needed)

## 底层执行器管理（Skill Runtime）

- `ai-log-converter/` 作为 Skill 底层执行器，由主仓库统一入口 `bun run log-convert` 调用。
- 统一入口位于 `src/cli/log-convert.ts`，负责参数透传、退出码透传和脚本路径稳定性。
- 推荐优先级：
  1. 同步开发、强一致发布：主仓库统一管理（当前模式）
  2. 独立发布节奏：拆为独立包（固定版本依赖）
  3. 必须保留独立 Git 历史：使用 Git Submodule（需维护 `.gitmodules` 和 pin 版本）
