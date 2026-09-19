# CodeWiki Handler — 代码知识文档（gongfeng）

CodeWiki 是工蜂基于 AI 对项目代码进行深度分析后，自动生成的结构化代码知识文档，包含「代码摘要」与「项目 Wiki」两部分。

## 通用约定

- `project_id` - 项目 ID 或项目完整路径（必填）
- **Git 与 SVN 差异**：Git 项目以 `branch` 定位；SVN 项目无分支概念，以 `doc_module_id` 定位并忽略 `branch`

---

## search_project_codewiki

检索项目的 CodeWiki 内容，默认在代码摘要与 Wiki 文档中全量检索。修改代码前可先用它了解已有实现与模块职责。

```
mcporter call gongfeng.search_project_codewiki project_id="<id|path>" query="AiFlowGuard"
```

- `project_id` - 项目 ID 或项目完整路径（必填）
- `query` - 检索关键词或自然语言描述（必填）
- `branch` - 分支名（可选），Git 项目缺省取默认分支；SVN 项目忽略
- `query_type` - 检索类型（可选），仅支持 `gongfeng_code`（代码摘要）/ `gongfeng_iwiki`（Wiki 文档），缺省为全量检索
- `doc_module_id` - 限定在指定模块内检索（可选）

返回命中片段数组，每项包含：`chunk_title`, `chunk_content`, `href`, `doc_file_path`, `doc_id`, `chunk_index`, `source`

---

## get_code_references

查询代码实体的引用链（调用图），查看谁引用了该实体（向上）以及它引用了什么（向下）。需要目标分支/commit 已完成 CodeWiki 代码分析。

```
mcporter call gongfeng.get_code_references project_id="<id|path>" branch="master" file_path="src/main/java/com/example/service/UserService.java" name="createUser"
```

- `project_id` - 项目 ID 或项目完整路径（必填）
- `branch` - 分支名（可选），与 `commit` 至少传一个
- `commit` - commit SHA（可选），与 `branch` 至少传一个，优先使用 commit 精确匹配
- `file_path` - 代码实体所在文件路径，相对于仓库根目录（必填）
- `line_number` - 代码实体所在行号（可选）
- `name` - 代码实体名称，如函数名、类名、全局变量名（必填）
- `doc_module_id` - 模块 ID（可选），不传则默认使用仓库级模块
- `depth_up` - 向上展开层数（谁引用了我），范围 0~5，默认 1。为0时不查询
- `depth_down` - 向下展开层数（我引用了谁），范围 0~5，默认 3。为0时不查询

返回包含 `target`（目标实体信息）、`up`（向上引用链）、`down`（向下引用链）的树形结构。若分析任务未就绪返回 `code: 404`。
