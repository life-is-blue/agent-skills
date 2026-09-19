# Issue Handler — 议题管理（gongfeng）

## create_issue

在项目中新建 Issue。

```
mcporter call gongfeng.create_issue \
  project_id="<id|path>" \
  title="<标题>" \
  [description="<描述>"] \
  [assignee_users="user1,user2"] \
  [confidential=true|false] \
  [labels="label1,label2"] \
  [tapd_info="--story=<id>"] \
  [tapd_id="<id>"] [tapd_type="story"|"bug"|"task"] [workspace_id=<id>]
```

---

## search_project_issues

搜索项目内 Issue。

```
mcporter call gongfeng.search_project_issues \
  project_id="<id|path>" \
  [iid=<IID>] \
  [search="<关键词>"] \
  [state="opened"|"closed"] \
  [order_by="created_at"|"updated_at"] \
  [sort="asc"|"desc"] \
  [created_after="2024-01-01T00:00:00%2B0800"] \
  [page=1] [per_page=10]
```

> ⚠️ 时间参数中 `+` 须转码为 `%2B`

---

## get_issue_detail

获取 Issue 详情（含关联 TAPD 工作项）。

```
mcporter call gongfeng.get_issue_detail project_id="<id|path>" issue_iid=<IID>
```

- `issue_iid` 是项目内 IID（用户可见编号）

---

## create_issue_note

给 Issue 添加评论。

```
mcporter call gongfeng.create_issue_note \
  project_id="<id|path>" \
  issue_id=<ISSUE-ID（非IID）> \
  note_message="<评论内容>"
```

> ⚠️ `issue_id` 是全局 ID，**不是** IID

---

## get_issue_notes

获取 Issue 评论列表。

```
mcporter call gongfeng.get_issue_notes \
  project_id="<id|path>" \
  issue_id=<ISSUE-ID> \
  [page=1] [per_page=10]
```

---

## update_issue

更新已有 Issue（标题、描述、状态、指派人等）。

```
mcporter call gongfeng.update_issue \
  project_id="<id|path>" \
  issue_iid=<IID> \
  [title="<新标题>"] \
  [description="<新描述>"] \
  [state_event="close"|"reopen"] \
  [assignee_users="user1,user2"] \
  [confidential=true|false] \
  [labels="label1,label2"] \
  [priority=<n>] \
  [tapd_info="--story=<id>"] \
  [tapd_id="<id>"] [tapd_type="story"|"bug"|"task"] [workspace_id=<id>]
```

- `state_event="close"` 关闭 Issue；`"reopen"` 重新打开

---

## update_issue_note

更新 Issue 的某条评论。

```
mcporter call gongfeng.update_issue_note \
  project_id="<id|path>" \
  issue_id=<ISSUE-ID> \
  note_id=<NOTE-ID> \
  note_message="<新内容>"
```

---

## get_project_review_labels

获取项目评审问题分类标签（用于代码审查评论打分类标签，如 CR-业务逻辑、CR-安全性等）。

```
mcporter call gongfeng.get_project_review_labels \
  project_id="<id|path>" \
  [include_ancestor_groups=false] \
  [order_by="name"|"created_at"] \
  [sort="asc"|"desc"] \
  [page=1] [per_page=20]
```

- 返回标签树，可直接将 `name` 传给 `create_merge_request_note` 或 `update_merge_request_note` 的 `labels` 字段
