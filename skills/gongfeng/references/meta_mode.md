# Meta 模式（工具发现与代理）

> ⚠️ **Meta 模式仅在 Streamable HTTP 服务中可用，stdio 模式不支持。**

## 概述

普通模式下，MCP 客户端连接时会一次性拿到全部约 50 个工具的完整列表（含所有 inputSchema），
工具数量多、Schema 体积大，会显著消耗大模型的上下文窗口。

Meta 模式将工具发现与工具执行解耦：客户端只看到 3 个元工具，具体工具由服务端向量语义检索
（`multilingual-e5-base` 模型，支持中英文混合）来匹配，**Schema 按需获取**。

### 开启方式

在 Streamable HTTP 请求头中加入：

```
X-Tool-Mode: meta
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "gongfeng": {
      "url": "https://mcpgw.knot.woa.com/gongfeng",
      "headers": {
        "Authorization": "Bearer tai_pat_xxx",
        "X-Tool-Mode": "meta"
      }
    }
  }
}
```

---

## 工具列表

### `lookup_gongfeng_tool`

#### 介绍

工蜂工具发现服务。通过语义搜索匹配所需的工蜂平台工具，返回匹配工具名称及相似度得分。

**重要：调用前请先提炼优化用户描述**

请将用户的原始需求提炼为简洁的"动作+对象"格式后再传入 `task_description`，以提升匹配准确性。

提炼示例：

| 用户原话 | 提炼后（传入本参数） |
|---------|------------------|
| "帮我看看这个仓库有哪些分支" | "查询分支列表" |
| "我想提一个 MR" | "创建合并请求" |
| "把这个文件的内容给我看看" | "获取文件内容" |
| "最近提交了哪些代码" | "查询提交列表" |
| "帮我查一下这个 commit 改了什么" | "获取提交差异" |

❌ 错误：直接传入用户原话"帮我看看最近仓库提了哪些代码改动"
✅ 正确：提炼后传入"查询提交列表"

#### 参数

- `task_description` (string, 必填)：提炼后的工蜂操作描述（非用户原话）。
- `top_k` (number, 可选)：返回工具数量（1-10，默认 3）。
- `similarity_threshold` (number, 可选)：相似度阈值（0.0-1.0，默认 0.8）。建议 0.6（高召回）到 0.8（高精确）。

#### 返回

```json
{
  "results": [
    {
      "name": "search_merge_request",
      "description": "Search merge request in a Gongfeng project",
      "score": 0.87
    }
  ]
}
```

若无匹配结果，返回：

```json
{
  "results": [],
  "message": "No matching tools found. Try rephrasing your task description."
}
```

---

### `get_tool_input_schema`

#### 介绍

查询指定工蜂 MCP 工具的参数 schema 信息。

**每次 lookup 后必须调用**：`lookup_gongfeng_tool` 的返回中不携带 inputSchema，必须通过本工具获取完整参数定义后才能执行。

#### 参数

- `tool_name` (string, 必填)：要查询的工具名称（来自 `lookup_gongfeng_tool` 返回的 `results[].name`）

#### 返回

成功时返回：

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string", "description": "仓库 ID 或 fullPath" },
      "state": { "type": "string", "description": "合并请求状态" }
    },
    "required": ["project_id"]
  }
}
```

工具名不存在时返回：

```json
{
  "error": "Unknown tool: xxx",
  "availableTools": ["search_projects", "create_branch", ...]
}
```

---

### `execute_gongfeng_tool`

#### 介绍

代理执行工蜂平台工具。必须先通过 `lookup_gongfeng_tool` 确定工具名，再通过 `get_tool_input_schema` 获取参数定义，最后用本工具执行。

#### 参数

- `tool_name` (string, 必填)：要执行的工具名称
- `arguments` (object, 必填)：传递给目标工具的参数，结构必须符合 `get_tool_input_schema` 返回的 `inputSchema`

#### 返回

与对应工具直接调用的返回格式完全一致。

若参数校验失败，返回错误信息及正确 schema：

```json
{
  "error": "Invalid arguments: project_id: Required",
  "inputSchema": { ... }
}
```

---

## 与普通模式的对比

| 对比维度 | 普通模式 | Meta 模式 |
|----------|----------|-----------|
| 工具列表大小 | ~50 个工具全量下发 | 仅 3 个元工具 |
| 上下文占用 | 高（所有 Schema 随列表下发） | 低（Schema 按需获取） |
| 调用步骤 | 直接调用（1 步） | lookup → getSchema → execute（固定 3 步） |
| 工具选择方 | 大模型自行从列表选择 | 服务端向量语义检索 |
| 可用范围 | stdio + Streamable HTTP | 仅 Streamable HTTP |

## 降级行为

- 若向量搜索超时或运行时出错，`lookup_gongfeng_tool` 自动降级为关键词匹配（精度略低）
- 若服务端模型加载失败，`X-Tool-Mode: meta` 请求头被忽略，服务端退回普通模式（返回全量工具列表）
