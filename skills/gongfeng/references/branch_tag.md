# Branch & Tag Handler — 分支与标签管理（gongfeng）

## create_branch

在工蜂项目中新建分支。

```
mcporter call gongfeng.create_branch project_id="<id|path>" branch_name="<name>" [ref="<source-branch-or-commit>"] [branch_type="<type>"] [description="<desc>"]
```

- `branch_name` - 新分支名称（必填）
- `ref` - 基于哪个分支/tag/commit 创建，默认默认分支
- `branch_type` - 分支类别，如 Mainline、Feature、Others（可选）
- `description` - 分支描述（可选）

---

## get_branch_list

获取工蜂项目的分支列表，支持模糊搜索和按最新提交时间过滤。

```
mcporter call gongfeng.get_branch_list project_id="<id|path>" [search="<keyword>"] [page=1] [per_page=20] [since="<datetime>"] [until="<datetime>"]
```

- `search` - 分支名模糊搜索（可选）
- `page` / `per_page` - 分页，默认 1/20，最大 100
- `since` - 仅返回活跃时间在此日期之后的分支（含当天，可选），格式 `2019-03-25T00:10:19+0800`
- `until` - 仅返回活跃时间在此日期之前的分支（含当天，可选），格式同 since

---

## get_branch_settings

获取工蜂项目的分支设置详情，包括分支命名规则与分支类型配置（如 Mainline、Feature、Others）。

```
mcporter call gongfeng.get_branch_settings project_id="<id|path>"
```

- 仅需 `project_id`
- 返回：`branch_name_regex`（分支命名正则）、`branch_name_regex_type`、`branch_types`（分支类型列表，含 name、description、color、enabled、regex）

---

## create_tag

在工蜂项目中创建新 Tag。

```
mcporter call gongfeng.create_tag project_id="<id|path>" tag="<tag-name>" start_point="<commit|branch|tag>" [tag_message="<message>"] [description="<desc>"] [labels="<label1,label2>"]
```

- `tag` - 新建 Tag 名称（必填）
- `start_point` - Tag 对应的 commit hash、分支名或已有 tag（必填）
- `tag_message` - Tag 附注信息，仅 tag 未被创建时有效（可选）
- `description` - Tag 描述（可选）
- `labels` - Tag 标签，多个标签用英文逗号分隔，最多 10 个（可选）。标签须预先在工蜂项目中创建（项目设置 → 标签），若标签不存在创建tag会失败

---

## get_tag_list

获取项目 tag 列表。

```
mcporter call gongfeng.get_tag_list project_id="<id|path>" [search="<keyword>"] [order_by="name"|"updated"] [sort="asc"|"desc"] [page=1] [per_page=20]
```

- `search` - 对 tag 名模糊搜索（可选）
- `order_by` - 排序字段：`name` 或 `updated`（默认 updated）
- `sort` - 排序方向：`asc` / `desc`（默认 desc）
- 分页默认 1/20，最大 100

---

## get_svn_repository_tree

获取 SVN 仓库目录树（仅 SVN 项目）。

```
mcporter call gongfeng.get_svn_repository_tree project_id="<id|path>" path="/" revision="HEAD"
```

- `path` - 目录路径，根目录用 `/`
- `revision` - 版本号，如 `HEAD` 或数字

---

## get_svn_file_raw

获取 SVN 仓库指定版本下文件的原始内容（仅 SVN 项目）。

```
mcporter call gongfeng.get_svn_file_raw \
  project_id="<id|path>" \
  file_path="/trunk/src/main.cpp" \
  [revision="HEAD"] [start_line=1] [end_line=100]
```

- `file_path` - 文件路径
- `revision` - 版本号，如 `HEAD` 或数字，默认 `HEAD`
- `start_line` / `end_line` - 可选，按行范围裁剪返回内容

---

## get_svn_commits

SVN 项目提交历史（分页）。

```
mcporter call gongfeng.get_svn_commits \
  project_id="<id|path>" \
  path="/" \
  [per_page=20] \
  [scroll_revision="<rev>"]
```

- `per_page` - 默认 20，最大 100
- `scroll_revision` - 滚动分页起点修订号

---

## get_svn_diff_files

获取 SVN 项目指定版本的文件变更列表（仅 SVN 项目）。

```
mcporter call gongfeng.get_svn_diff_files \
  project_id="<id|path>" \
  revision="HEAD" \
  path="/" \
  [include_diff_content=false]
```

- `revision` - 版本号，如 `HEAD` 或数字
- `path` - 目录路径，根目录用 `/`
- `include_diff_content` - 是否包含 diff 内容（默认 `false`，仅返回文件变更列表）

---

## get_svn_diff_detail

获取 SVN 项目任意两个版本之间的文件差异详情（仅 SVN 项目）。

```
mcporter call gongfeng.get_svn_diff_detail \
  project_id="<id|path>" \
  path="/" \
  new_revision="HEAD" \
  [old_revision="<rev>"] \
  [old_path="<path>"] \
  [expand=false]
```

- `path` - 文件或目录路径，根目录用 `/`
- `new_revision` - 新版本号，如 `HEAD` 或数字
- `old_revision` - 旧版本号，不填时默认取新版本的上一个版本
- `old_path` - 旧版本路径，不填时默认与 `path` 相同
- `expand` - 是否展开折叠的 diff 内容（默认 `false`）

---

## create_svn_file

向 SVN 版本库新建文件并写入内容（需写权限）。

```
mcporter call gongfeng.create_svn_file \
  project_id="<id|path>" \
  file_path="/trunk/src/new_file.txt" \
  content="<内容>" \
  [encoding="text"] \
  commit_message="<提交信息>"
```

- `file_path` - 文件路径
- `content` - 文件内容
- `encoding` - 内容编码，可选 `text`、`base64`，默认 `text`
- `commit_message` - 提交信息

---

## update_svn_file

更新 SVN 版本库中已有文件的内容（需写权限），建议传 `base_rev` 做乐观锁校验。

```
mcporter call gongfeng.update_svn_file \
  project_id="<id|path>" \
  file_path="<文件路径>" \
  [base_rev=123] \
  content="<内容>" \
  [encoding="text"] \
  commit_message="<提交信息>"
```

- `base_rev` - 基础版本号，用于乐观锁校验，文件被他人修改则提交失败
- `encoding` - 内容编码，可选 `text`、`base64`，默认 `text`

---

## batch_edit_svn_files

在一次提交中原子完成新增/修改/删除多个文件（需所有涉及路径写权限）。

```
mcporter call gongfeng.batch_edit_svn_files \
  project_id="<id|path>" \
  commit_message="<提交信息>" \
  file_changes='[{"path":"/trunk/a.txt","change_type":"add","content":"<Base64>","encoding":"base64"}]'
```

- `file_changes` - 文件变更列表数组，每个元素含 `path`、`change_type`(add/modify/delete/proponly)、`content`(add/modify 时 Base64 编码)、`encoding`、`base_rev`、`prop_changes` 等字段；CLI 传参时可用如上 JSON 字符串，服务会自动解析为数组

---

## create_svn_branch

在 SVN 项目内创建分支，目标路径需在 `/branches` 目录下（需 `source_path` 读写权限）。

```
mcporter call gongfeng.create_svn_branch \
  project_id="<id|path>" \
  source_path="/trunk" \
  target_path="/branches/feature-x" \
  [revision=123] \
  [import_permissions=true] \
  message="<提交信息>"
```

- `source_path` - 源分支路径，即被复制的分支
- `target_path` - 新分支路径，需在 `/branches` 目录下
- `import_permissions` - 是否导入源分支权限

---

## create_svn_review

在 SVN 项目中新建一个代码在服务器的评审（CR）。

```
mcporter call gongfeng.create_svn_review \
  project_id="<id|path>" \
  title="<标题>" \
  review_path="<代码路径>" \
  source_revision="<源版本号>" \
  target_revision="<目标版本号>" \
  [description="<描述>"] \
  [labels="a,b"] \
  [reviewer_ids="user1,123"] \
  [approver_rule=1] \
  [selected_files='["/a.txt"]']
```

- `approver_rule` - 评审人规则：-1 所有评审人通过、1 单评审通过、2+ 多评审通过
- `selected_files` - 指定需要评审的文件路径数组，为空时默认所有文件

---

## list_svn_reviews

在 SVN 项目内获取代码评审（CR）列表，支持多种过滤条件并分页。

```
mcporter call gongfeng.list_svn_reviews \
  project_id="<id|path>" \
  [state="opened"] \
  [reviewable_type="commit"] \
  [author_id=123] \
  [reviewer_id=456] \
  [labels="a,b"] \
  [iids='[1,2]'] \
  [order_by="created_at"] \
  [sort="desc"] \
  [page=1] \
  [per_page=20]
```

- `state` - 评审状态过滤，如 `opened`、`approving`、`approved`、`change_denied`、`closed`
- `reviewable_type` - 评审类型过滤，如 `commit`、`branch`
- `author_id` / `reviewer_id` - 按创建人 / 评审人 id 过滤
- `labels` - 按标签过滤，多个用英文逗号分隔
- `iids` - 按评审在项目中的序号 iid 数组过滤
- `order_by` / `sort` - 排序字段与方向
- `per_page` - 每页大小，默认 20，最大 100

---

## get_svn_review_note

在 SVN 项目内查看某个指定代码评审的指定评论。

```
mcporter call gongfeng.get_svn_review_note \
  project_id="<id|path>" \
  review_id=123 \
  note_id=456
```

---

## list_svn_review_notes

在 SVN 项目内获取某个指定代码评审的评论列表（分页）。

```
mcporter call gongfeng.list_svn_review_notes \
  project_id="<id|path>" \
  review_id=123 \
  [page=1] \
  [per_page=20]
```

- `per_page` - 每页大小，默认 20，最大 100

---

## create_svn_review_note

在 SVN 项目内对某个指定代码评审创建评论，行内评论时需填 `path` 和 `line`。

```
mcporter call gongfeng.create_svn_review_note \
  project_id="<id|path>" \
  review_iid=1 \
  body="<评论内容>" \
  [path="/a.txt"] \
  [line=10] \
  [line_type="new"] \
  [risk=0] \
  [resolve_state=0]
```

- `review_iid` - 代码评审在项目中的序号 iid
- `line_type` - 行类型：`new` 新增行、`old` 删除行
- `risk` - 风险等级：0 无（默认）、1 轻微、2 一般、3 严重
- `resolve_state` - 解决状态：0 默认、1 未解决、2 已解决

---

## update_svn_review_note

在 SVN 项目内修改某个指定代码评审的指定评论。

```
mcporter call gongfeng.update_svn_review_note \
  project_id="<id|path>" \
  review_iid=1 \
  note_id=456 \
  [body="<更新内容>"] \
  [risk=1] \
  [resolve_state=2]
```

- `review_iid` - 代码评审在项目中的序号 iid
- `risk` - 风险等级：0 无、1 轻微、2 一般、3 严重
- `resolve_state` - 解决状态：0 默认、1 未解决、2 已解决
