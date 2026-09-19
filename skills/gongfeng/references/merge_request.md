# Merge Request Handler — 合并请求管理（gongfeng）

## create_merge_request

创建 MR。

```
mcporter call gongfeng.create_merge_request \
  project_id="<id|path>" \
  title="<title>" \
  source_branch="<feature>" \
  target_branch="<master>" \
  [description="<desc>"] \
  [target_project_id=<id>] \
  [tapd_info="--story=<id>"] \
  [tapd_id="<id>"] [tapd_type="story"|"bug"|"task"] [workspace_id=<id>] \
  [reviewers="user1,user2"] \
  [necessary_reviewers="user3"] \
  [approver_rule=<-1|1|>=2>] \
  [necessary_approver_rule=<-1|0|1|>=2>] \
  [labels="label1,label2"]
```

> 审批规则（可选，仅作用于对应评审人）：
> - `approver_rule`：`-1` 所有评审人通过；`1` 单评审通过；`>=2` 需要对应数量的评审人通过。
> - `necessary_approver_rule`：`-1` 所有必要评审人通过；`1` 单必要评审通过；`>=2` 需要对应数量的必要评审人通过；`0` 不需要必要评审人即可通过。
> - ⚠️ 若非用户指定，请勿传入这两个参数。

---

## search_merge_request

在项目内搜索 MR。

```
mcporter call gongfeng.search_merge_request project_id="<id|path>" \
  [iid=<IID>] \
  [source_branch="<branch>"] \
  [target_branch="<branch>"] \
  [state="opened"|"merged"|"closed"|"reopened"] \
  [milestone="<milestone_title>"] \
  [order_by="created_at"|"updated_at"|"resolve_at"] \
  [sort="asc"|"desc"] \
  [created_after="2024-01-01T00:00:00%2B0800"] \
  [page=1] [per_page=8]
```

> ⚠️ 时间参数中 `+` 须转码为 `%2B`

---

## search_merge_request_by_user

按用户（指派/作者/评审）全局搜索 MR。

```
mcporter call gongfeng.search_merge_request_by_user \
  [assignee_user_name="<user>"] \
  [author_user_name="<user>"] \
  [reviewer_user_name="<user>"] \
  [state="opened"|"merged"|"closed"|"reopened"|"all"] \
  [sort="created_desc"|"created_asc"|"updated_desc"|"updated_asc"] \
  [page=1] [per_page=10]
```

---

## get_merge_request_changes

获取 MR 代码变更。

```
mcporter call gongfeng.get_merge_request_changes \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）> \
  [diff_file_only=true] \
  [filter_files=["src/","README.md"]]
```

- `merge_request_id` 是全局 ID，**不是** IID
- `diff_file_only=true` 只返回文件路径列表
- `filter_files`：只返回匹配路径；**目录必须以 `/` 结尾**（如 `src/`），也可传单个文件的完整路径

---

## get_review_by_merge_request_iid

按 MR 的 **IID** 查询对应的 review 信息，包含 review.id 以及 review.iid 的信息。

```
mcporter call gongfeng.get_review_by_merge_request_iid \
  project_id="<id|path>" \
  merge_request_iid=<IID>
```


---

## get_review_intelligent_result

获取指定 Review 的 AI CR 评论结果。`review_iid` 与 `merge_request_iid` 二选一（互斥），同时为空会被拒绝。

```
mcporter call gongfeng.get_review_intelligent_result \
  project_id="<id|path>" \
  review_iid=<REVIEW-IID> \
  [patch_set_num=<PATCH-SET-NO>] \
  [include_accepted=true] \
  [include_abandoned=true]
```

只有 MR IID、没有 review IID 时（最常见场景：Agent 拿到 MR 链接），用 `merge_request_iid` 走 handler 内置兜底：

```
mcporter call gongfeng.get_review_intelligent_result \
  project_id="<id|path>" \
  merge_request_iid=<MR-IID>
```

- 需要 `think_result` 时用 JSON 参数：`--args '{"project_id":"group/repo","review_iid":1,"include_think_result":true}'`（默认省略思考过程字段）

- `review_iid` 是项目内的 **IID**，不是全局 `review_id`
- `merge_request_iid` 是 MR 的项目内 IID；handler 会静默调 `get_review_by_merge_request_iid` 解析出 `review.iid` 后再请求 AI CR，调用方拿到的是同一份 AI 评审结果
- 不传 `patch_set_num` 时，默认返回最新修订集的 AI 评论结果
- `include_accepted=true` 时，结果中可能包含 `accepted_comments`
- `include_abandoned=true` 时，结果中可能包含 `abandoned_comments`
- 当没有 AI 评论时，`comments`、`accepted_comments`、`abandoned_comments` 字段可能不存在
- 返回体除原始 `status` 外，旁置注入 `status_text` 中文释义，覆盖业务码 `-1/0/1/2/3/999/1000/1001`（`1001=NO_HISTORY` 表示该 MR 暂无 AI 评审历史）；未知码降级为 `未知业务码（status=N）`，不抛错

---

## search_merge_request_notes

获取 MR 评论列表。

```
mcporter call gongfeng.search_merge_request_notes \
  project_id="<id|path>" \
  merge_request_id=<MR-ID> \
  [system=false] \
  [sort="created_asc"|"created_desc"] \
  [resolve_states=0|1|2] \
  [page=1] [per_page=10]
```

- `system`：不传/`null`=全部，`true`=仅系统评论，`false`=仅非系统评论
- `resolve_states`：**number 数组**，元素为 `0`（default）、`1`（unresolved）、`2`（resolved）；不传则全部状态

---

## create_merge_request_note

给 MR 添加评论（可指定文件行）。

```
mcporter call gongfeng.create_merge_request_note \
  project_id="<id|path>" \
  merge_request_id=<MR-ID> \
  body="<评论内容>" \
  [path="src/foo.ts"] \
  [line=42] \
  [line_type="old"|"new"] \
  [risk=0|1|2|3] \
  [resolve_state=0|1|2] \
  [labels=["bug","perf"]] \
  [is_person_note=false] \
  [notify_enabled=true]
```

- `labels`：评审标签名称列表；不传则不向接口发送标签
- `risk`: 0=默认, 1=轻微, 2=一般, 3=严重
- `is_person_note=true` 记录到 comments tab；否则进 conversation tab

---

## reply_merge_request_note

回复 MR 的某条评论。

```
mcporter call gongfeng.reply_merge_request_note \
  project_id="<id|path>" \
  merge_request_id=<MR-ID> \
  note_id=<NOTE-ID> \
  body="<回复内容>" \
  [notify_enabled=true] \
  [resolve_state=0|1|2]
```

> ⚠️ 只能回复代码行上的第一条评论，不支持回复已是回复的评论

---

## update_merge_request_note

编辑 MR 已有评论。

```
mcporter call gongfeng.update_merge_request_note \
  project_id="<id|path>" \
  merge_request_id=<MR-ID> \
  note_id=<NOTE-ID> \
  body="<新正文>" \
  [risk=0|1|2|3] \
  [resolve_state=0|1|2] \
  [labels=["bug","perf"]] \
  [notify_enabled=true]
```

- 对应工蜂接口：`PUT /api/v3/projects/:id/merge_requests/:merge_request_id/notes/:note_id`
- **必填**：`project_id`、`merge_request_id`、`note_id`、`body`
- **`labels`**：评审标签名称列表。**不传**时沿用已有标签；**传 `[]`** 则清空该评论上的标签
- `risk` / `resolve_state`：接口文档可能写 string，MCP 使用 **number**（0–3 / 0–2），与 OpenAPI 及返回 JSON 一致
- `notify_enabled`：OpenAPI 中有，可选

---

## update_merge_request

更新已有 MR（标题、描述、状态等）。

```
mcporter call gongfeng.update_merge_request \
  project_id="<id|path>" \
  merge_request_id=<MR-ID> \
  [title="<新标题>"] \
  [description="<新描述>"] \
  [state_event="close"|"reopen"] \
  [tapd_info="--story=<id>"] \
  [tapd_id="<id>"] [tapd_type="story"|"bug"|"task"] [workspace_id=<id>] \
  [labels="label1,label2"] \
  [assignee_id=<id>] \
  [target_branch="<branch>"] \
  [source_branch="<branch>"]
```

- `state_event="close"` 关闭 MR；`"reopen"` 重新打开

---

## merge_merge_request

合并一个 MR。

```
mcporter call gongfeng.merge_merge_request \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）> \
  [merge_commit_message="<自定义合并提交信息>"] \
  [merge_type="merge"|"squash"|"rebase_merge"]
```

- `merge_request_id` 是全局 ID，**不是** IID
- `merge_type`：`merge`（默认合并）、`squash`（压缩合并）、`rebase_merge`（变基合并）

---

## batch_invite_mr_reviewer

批量邀请评审人（普通评审人或必要评审人）到 MR。

```
mcporter call gongfeng.batch_invite_mr_reviewer \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）> \
  [reviewers="user1,user2"] \
  [necessary_reviewers="user3,user4"]
```

- `merge_request_id` 是全局 ID，**不是** IID
- `reviewers`：普通评审人用户名，多个用英文逗号分隔
- `necessary_reviewers`：必要评审人用户名，多个用英文逗号分隔
- 用户名会自动解析为 user_id；`reviewers` 与 `necessary_reviewers` 至少需提供其一

---

## dismiss_mr_reviewer

从 MR 移除某个评审人。后端会自动识别该用户当前的评审人类型（普通评审人或必要评审人）。

```
mcporter call gongfeng.dismiss_mr_reviewer \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）> \
  reviewer="<username>"
```

- `merge_request_id` 是全局 ID，**不是** IID
- `reviewer`：要移除的评审人用户名（英文名），自动解析为 user_id
- 一次调用只移除一个评审人；如需移除多个，请多次调用

---

## submit_mr_review_summary

评审人对 MR 发表评审意见，用于流转评审状态。

```
mcporter call gongfeng.submit_mr_review_summary \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）> \
  reviewer_event="comment"|"approve"|"require_change"|"deny" \
  summary="<评审意见摘要>"
```

- `merge_request_id` 是全局 ID，**不是** IID
- `reviewer_event`：评审人事件
  - `comment`：仅留言/评论（不改变评审状态）
  - `approve`：通过
  - `require_change`：要求修改
  - `deny`：拒绝
- `summary`：评审意见摘要（**必填**，不能为空）
- 调用方需是该 MR 的评审人，否则后端会拒绝

---

## reopen_mr_review

重置/重新打开 MR 的评审状态。仅当 MR 评审状态为 `denied`（拒绝）或 `require_change`（要求修改）时可用，重置后评审人可再次评审。

```
mcporter call gongfeng.reopen_mr_review \
  project_id="<id|path>" \
  merge_request_id=<MR-ID（非IID）>
```

- `merge_request_id` 是全局 ID，**不是** IID
- 仅在评审状态为 `denied`、`require_change` 时生效；其他状态调用后端会返回错误
