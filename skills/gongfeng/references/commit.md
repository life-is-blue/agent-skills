# Commit Handler — 提交管理（gongfeng）

## get_commits_list

获取项目提交列表。

```
mcporter call gongfeng.get_commits_list \
  project_id="<id|path>" \
  [ref_name="<branch|tag>"] \
  [path="<file-path>"] \
  [since="2024-01-01T00:00:00%2B0800"] \
  [until="2024-12-31T23:59:59%2B0800"] \
  [page=1] [per_page=10]
```

> ⚠️ 时间参数中 `+` 须转码为 `%2B`

---

## get_commit_info

获取单个 commit 详情。

```
mcporter call gongfeng.get_commit_info project_id="<id|path>" commit_sha="<sha>"
```

---

## get_commit_refs

获取与指定 commit 关联的分支和标签。

```
mcporter call gongfeng.get_commit_refs \
  project_id="<id|path>" \
  commit_sha="<sha>" \
  [type="all"] \
  [page=1] [per_page=10]
```

- `type`：引用类型，可选 `branch`（仅分支）、`tag`（仅标签）、`all`（全部，默认）

---

## get_commit_diff

获取 commit 的 diff。

```
mcporter call gongfeng.get_commit_diff \
  project_id="<id|path>" \
  sha="<commit-sha|branch|tag>" \
  [path="<file>"] \
  [diff_file_only=true]
```

- `diff_file_only=true` 先获取文件列表，再针对特定文件拉详细 diff，适合大 commit

---

## cherry_pick_commits

将多个提交 cherry-pick 到目标分支；可选创建 MR。

```
mcporter call gongfeng.cherry_pick_commits \
  project_id="<id|path>" \
  commits='["abc123","def456"]' \
  target_branch="<branch>" \
  title="<MR title>" \
  [create_mr=true] \
  [description="<desc>"] \
  [labels="a,b"] \
  [reviewers="1,2"] \
  [necessary_reviewers="3"] \
  [assignee_id=<id>] \
  [approver_rule=-1] \
  [necessary_approver_rule=0] \
  [workspace_id=<id>] [tapd_id="<id>"] [tapd_type="story"] [tapd_info="--story=1 hhh"]
```

- `approver_rule`：`-1` 全部、`1` 单人、`>=2` 多人
- `necessary_approver_rule`：同上，或 `0` 表示无

---

## compare

比较两个分支/tag/commit 之间的差异。

```
mcporter call gongfeng.compare \
  project_id="<id|path>" \
  from="<source-branch>" \
  to="<target-branch>" \
  [path="<file>"] \
  [straight=false] \
  [only_count=false] \
  [diff_file_only=false] \
  [filter_files=["src/","README.md"]]
```

- `straight=true` 不含合并提交的直接比较
- `only_count=true` 只返回统计信息
- `diff_file_only=true` 只返回文件路径列表

---

## revert_commit

还原指定分支的某个提交。

```
mcporter call gongfeng.revert_commit \
  project_id="<id|path>" \
  sha="<commit-sha>" \
  branch="<target-branch>" \
  [dry_run=false]
```

- `dry_run=true` 预检查是否有冲突，不实际提交

---

## get_commit_review_list

获取项目中所有的 Commit 评审（代码评审），支持按作者、状态、标签过滤及分页。

```
mcporter call gongfeng.get_commit_review_list \
  project_id="<id|path>" \
  [author_id=<USER-ID>] \
  [state="approving"|"approved"|"change_required"|"closed"] \
  [labels="label1,label2"] \
  [order_by="created_at"|"updated_at"] \
  [sort="asc"|"desc"] \
  [page=1] [per_page=10]
```

- 不传 `state` 时返回所有状态的评审
- `labels` 多个标签用英文逗号分隔
- 返回 Commit 评审列表，每条包含 title、description、commits、reviewers、state 等信息

---

## get_commit_review_detail

按 IID 获取项目中某个具体的 Commit 评审详情。

```
mcporter call gongfeng.get_commit_review_detail \
  project_id="<id|path>" \
  review_iid=<REVIEW-IID>
```

- `review_iid` 是项目内的 **IID**，不是全局 `review_id`

---

## create_commit_review

基于源分支和目标分支创建 Commit Review。

```
mcporter call gongfeng.create_commit_review \
  project_id="<id|path>" \
  title="<title>" \
  source_branch="<source-branch>" \
  target_branch="<target-branch>" \
  [source_commit="<source-sha>"] \
  [target_commit="<target-sha>"] \
  [reviewers="alice,bob"] \
  [necessary_reviewers="carol"] \
  [approver_rule=-1] \
  [necessary_approver_rule=0] \
  [selected_files='["src/index.ts"]']
```

- `source_branch`、`target_branch` 为必填。
- `source_commit`、`target_commit` 可选；不传则默认选择该分支最新的提交点。
- `reviewers`、`necessary_reviewers` 使用用户名，多个以英文逗号分隔。
- `approver_rule`：`-1` 全部评审人通过、`1` 单人通过、`>=2` 需要多位通过。
- `necessary_approver_rule`：同上，或 `0` 表示不需要必要评审人。
- 可选传入 `description`、`target_project_id`（跨项目评审）、`labels`（CR 自身标签，逗号分隔字符串）、`auto_intelligent_review_enabled`（启用智能评审）、TAPD 字段。
- 返回的 `id` 即后续评论/回复/评审意见/重开操作所需的**全局 `review_id`**，也可从 `get_commit_review_detail` / `get_commit_review_list` 返回的 `id` 字段获取。

---

## search_commit_review_notes

查询 Commit Review 的评论和讨论记录。

```
mcporter call gongfeng.search_commit_review_notes \
  project_id="<id|path>" \
  review_id=<REVIEW-ID> \
  [page=1] [per_page=10]
```

- `review_id` 是全局 ID，不是项目内 `review_iid`；可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。

---

## get_commit_review_note

查询 Commit Review 的单条评论。

```
mcporter call gongfeng.get_commit_review_note \
  project_id="<id|path>" \
  review_id=<REVIEW-ID> \
  note_id=<NOTE-ID>
```

- `review_id` 是全局 ID，不是项目内 `review_iid`；可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。

---

## create_commit_review_note

创建 Commit Review 的全局或行内评论。

```
mcporter call gongfeng.create_commit_review_note \
  project_id="<id|path>" \
  review_id=<REVIEW-ID> \
  body="<comment>" \
  [path="src/index.ts"] [line=10] [line_type="new"] \
  [labels='["CR-业务逻辑"]']
```

- 创建行内评论时，需同时传入 `path`、`line`、`line_type`（`old`/`new`）。
- `risk`：0 default、1 slight、2 normal、3 serious。
- `resolve_state`：0 default、1 unresolved、2 resolved。
- `labels` 为评审问题分类标签名称数组（如 `CR-业务逻辑`，可用 `get_project_review_labels` 查可用标签），与 `create_commit_review` 的 `labels`（CR 自身标签，逗号分隔字符串）不同。
- `review_id` 为全局 ID，可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。

---

## reply_commit_review_note

回复 Commit Review 中已有的评论。

```
mcporter call gongfeng.reply_commit_review_note \
  project_id="<id|path>" \
  review_id=<REVIEW-ID> \
  note_id=<NOTE-ID> \
  body="<reply>"
```

- `review_id` 为全局 ID，可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。
- 回复的评论必须是评论在代码行上的第一条评论，不支持回复已经是回复的评论。

---

## update_commit_review_note

编辑 Commit Review 的已有评论。

```
mcporter call gongfeng.update_commit_review_note \
  project_id="<id|path>" \
  review_id=<REVIEW-ID> \
  note_id=<NOTE-ID> \
  body="<updated-comment>" \
  [labels='["CR-业务逻辑"]']
```

- `review_id` 为全局 ID，可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。
- 可选传入 `risk`（0–3）、`resolve_state`（0–2）、`notify_enabled`。
- `labels` 不传时沿用已有标签；传空数组 `[]` 可清空标签。

---

## reopen_commit_review

重开或重置 Commit Review 的评审状态。

```
mcporter call gongfeng.reopen_commit_review \
  project_id="<id|path>" \
  review_id=<REVIEW-ID>
```

- `review_id` 是全局 ID，不是项目内 `review_iid`；可从 `create_commit_review` 返回的 `id` 或 `get_commit_review_detail` 的 `id` 字段获取。

---

## close_commit_review

关闭 Commit Review 评审单，将其状态转为 `closed` 终态。

```
mcporter call gongfeng.close_commit_review \
  project_id="<id|path>" \
  review_id=<REVIEW-ID>
```

- `review_id` 是全局 ID，不是项目内 `review_iid`；可从 `create_commit_review` / `get_commit_review_detail` / `get_commit_review_list` 返回的 `id` 字段获取。
- 关闭后 `state` 字段为 `closed`，可用 `reopen_commit_review` 重开。

---

## get_commit_combined_status

获取某个 commit ref（SHA、分支名或 tag）的流水线/CI 综合检查状态，包含各检查项的详情（名称、状态、描述、链接），对应 MR 页面的「检查成功/失败」区域。

```
mcporter call gongfeng.get_commit_combined_status \
  project_id="<id|path>" \
  ref="<sha|branch|tag>" \
  [target_branch="<target-branch>"] \
  [page=1] [per_page=20]
```

- `ref`：可以是 commit SHA、分支名或 tag 名
- `target_branch`：可选，按 MR 目标分支过滤检查项

---

## add_commit_check

新建检测结果：为某个 commit / 分支 / tag 上报提交检查（流水线、CI、人工审批）状态。

```
mcporter call gongfeng.add_commit_check \
  project_id="<id|path>" \
  sha="<sha|branch|tag>" \
  state="<pending|success|error|failure|need_approve>" \
  target_url="<pipeline-url>" \
  description="<desc>" \
  [context="<label>"] [detail="<markdown>"] [block=true]
```

- `state`、`target_url`、`description` 均为必填
- `state`：`pending` 检查中、`success` 通过、`error` 检测出错、`failure` 检查不通过、`need_approve` 等待人工审批
- `context`：区别于其他检测系统的标签，默认 `default`；覆盖已有检测结果需流水线名称、token、`context` 一致
- `block`：是否锁住提交和合并请求，默认 `false`
- `target_branches`：可选数组，为空时展示在所有 MR，传入 `~NONE` 则不展示在任一 MR
- `approvals`：可选数组，`state=need_approve` 时有意义，最多 20 条，每项含 `approve_url`、`approver_users`、`quick_approve_enabled`（0/1）

