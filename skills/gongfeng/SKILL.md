---
name: gongfeng
description: "工蜂（Gongfeng）代码平台 MCP skill，提供仓库管理、分支操作、合并请求、议题管理、代码审查、文件读写、提交查询等能力。当用户提到「工蜂」「gongfeng」「代码仓库」「MR/合并请求」「创建分支」「查看提交」「查看文件」「创建 issue」等代码平台操作时触发。"
---

# gongfeng Skill

工蜂（Gongfeng）代码平台的 MCP 操作指南。所有工具均通过 `mcporter` 调用。

## ⚠️ 前置条件

所有工具必须通过 `mcporter` 调用，**不能直接调用 MCP 工具**：

如果遇到mcporter调用问题，可以参考`references/mcporter.md`

```bash
# ✅ 正确
mcporter call gongfeng.<工具名> <参数>

# ❌ 错误（会失败）
直接调用 gongfeng.xxx
```

首次使用前运行检查脚本：

```bash
bash skill/scripts/check-mcporter.sh
```

---

## 接入方式

### 太湖统一认证

需要在太湖平台申请个人令牌（TAI_TOKEN）：[前往申请](https://tai.it.woa.com/user/pat)

获取令牌后，在 MCP 配置中添加 `headers` 字段：

```json
{
  "mcpServers": {
    "gongfeng": {
      "url": "https://mcpgw.knot.woa.com/gongfeng",
      "headers": {
        "Authorization": "Bearer tai_pat_xxx"
      }
    }
  }
}
```

> `tai_pat_xxx` 替换为您在太湖平台申请的个人令牌。

### 只读模式（可选）

开启只读模式后，MCP 服务器只会暴露**查询类工具**，所有写操作工具（创建/更新/删除文件、创建分支、创建合并请求、创建 issue、cherry-pick、revert 等）将不再对外提供，适合只需要查询能力、希望规避误操作风险的场景。

在请求头中加入 `X-Readonly: true` 即可开启：

```json
{
  "mcpServers": {
    "gongfeng": {
      "url": "https://mcpgw.knot.woa.com/gongfeng",
      "headers": {
        "Authorization": "Bearer tai_pat_xxx",
        "X-Readonly": "true"
      }
    }
  }
}
```

只读模式下可用的工具包括：`search_projects`、`search_project_code`、`get_file_base64_content`、`get_repository_tree`、`get_blob_content`、`get_user_info`、`get_current_user`、`get_project_members`、`get_commit_info`、`get_commit_refs`、`get_commits_list`、`get_commit_diff`、`get_file_blame`、`search_merge_request`、`search_merge_request_notes`、`search_merge_request_by_user`、`get_merge_request_changes`、`get_review_by_merge_request_iid`、`get_review_intelligent_result`、`search_project_issues`、`get_issue_detail`、`get_issue_notes`、`get_tapd_workitems`、`get_tag_list`、`get_svn_repository_tree`、`get_svn_file_raw`、`get_svn_commits`、`get_svn_diff_files`、`get_svn_diff_detail`、`compare`、`get_project_detail`、`get_user_events`、`search_namespaces`、`get_review_rule_config`、`get_review_rules_by_files`、`get_review_rule_detail`、`get_commit_review_list`、`get_commit_combined_status`、`get_project_review_labels`、`search_project_codewiki`、`get_code_references`。

### 工具子集过滤（可选）

通过请求头 `X-Tool-Set` 可将客户端可见及可调用的工具限定为指定子集，适合只需要部分工具、希望缩减大模型工具上下文的场景。

格式为逗号分隔的工具名列表：

```json
{
  "mcpServers": {
    "gongfeng": {
      "url": "https://mcpgw.knot.woa.com/gongfeng",
      "headers": {
        "Authorization": "Bearer tai_pat_xxx",
        "X-Tool-Set": "create_merge_request,search_merge_request,create_issue"
      }
    }
  }
}
```

- list_tools 与 call_tool 均受该过滤限制，不在集合内的工具无法被发现也无法被调用。
- 优先级高于 `X-Readonly`：当 `X-Tool-Set` 生效时，工具列表完全以该 header 指定的子集为准，`X-Readonly` 不叠加。
- header 为空或未设置时不生效，行为与不传完全一致。

### Meta 模式（可选，仅 Streamable HTTP）

在请求头中加入 `X-Tool-Mode: meta` 可开启 Meta 模式。开启后客户端只会看到 3 个元工具（`lookup_gongfeng_tool` / `get_tool_input_schema` / `execute_gongfeng_tool`），由服务端语义检索代替大模型自行从 ~50 个工具中选择，可显著节省上下文。

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

详细用法见 `references/meta_mode.md`。

---

## 工具索引（按 Handler 分类）

| Handler | 说明 | Reference |
|---------|------|-----------|
| Meta 模式 | 工具发现与代理：用自然语言搜索工具、获取参数 schema、代理执行（**仅 Streamable HTTP**） | `references/meta_mode.md` |
| Project | 项目/仓库管理：搜索、新建、成员列表、目录树、TAPD 关联、标签管理 | `references/project.md` |
| Branch & Tag | 分支和标签管理：创建分支、tag 列表、SVN 目录树与提交历史 | `references/branch_tag.md` |
| Merge Request | 合并请求全生命周期：创建、查询、更新、评论、代码审查 | `references/merge_request.md` |
| Issue | 议题管理：创建、查询、更新、评论 | `references/issue.md` |
| Commit | 提交管理：列表、详情、引用查询、diff、cherry-pick、比较、还原、代码评审 | `references/commit.md` |
| File | 文件操作：blob、创建/更新、批量修改、blame | `references/file.md` |
| User | 用户信息：当前用户、按 ID/名查询 | `references/user.md` |
| CodeWiki | 代码知识文档：检索代码摘要与 Wiki 内容、查询代码引用链（调用图） | `references/codewiki.md` |

---

## 快速示例

```bash
# 搜索项目
mcporter call gongfeng.search_projects search="tgit-mcp-server"

# 查看当前用户
mcporter call gongfeng.get_current_user

# 创建分支
mcporter call gongfeng.create_branch project_id="tgit/tgit-mcp-server" branch_name="feat/my-feature" ref="master"

# 查看文件内容
mcporter call gongfeng.get_blob_content project_id="tgit/tgit-mcp-server" sha="master" file_path="README.md"

# 创建 MR
mcporter call gongfeng.create_merge_request project_id="tgit/tgit-mcp-server" title="feat: xxx" source_branch="feat/my-feature" target_branch="master"
```

---

## 通用参数约定

| 参数 | 说明 |
|------|------|
| `project_id` | 项目 ID（数字）或完整路径，如 `tgit/tgit-mcp-server` |
| `page` / `per_page` | 分页，默认 1 / 10 |
| 时间格式 | ISO 8601，`+` 须转码为 `%2B`，如 `2024-03-25T00:00:00%2B0800` |
| ID vs IID | **ID** = 全局唯一；**IID** = 项目内可见编号。部分接口要求 ID，注意区分 |
| 评审(review) vs 合并请求(mr, merge_request) | **review** = 代码审查；**mr** = 合并请求 ，部分接口需要 review_id 或者 review_iid, 指的是 review 的 id 或者 iid. 注意区分 |

---

## 需要更多细节？

按需加载对应 reference 文件，例如查看 MR 相关所有工具：

```
read skill/references/merge_request.md
```

查看 Meta 模式的三个元工具及调用流程：

```
read skill/references/meta_mode.md
```
