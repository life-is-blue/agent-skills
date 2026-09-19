# Project Handler — 项目/仓库管理（gongfeng）

## search_projects

搜索工蜂项目。

```
mcporter call gongfeng.search_projects [search="关键词"] [type="GIT"|"SVN"] [page=1] [per_page=10]
```

- `search` - 搜索关键词（可选）
- `type` - 项目类型 GIT 或 SVN（可选）
- `page` / `per_page` - 分页（默认 1 / 10）

返回字段：`id`, `name`, `path`, `fullPath`, `description`, `defaultBranch`, `visibilityLevel`

---

## search_project_code

在单个工蜂项目内做代码文本搜索（对应 `GET /api/web/v1/search/projects/{projectId}/code`）。

```
mcporter call gongfeng.search_project_code project_id="6368" search="<keyword>" [page=1] [per_page=20]
```

- `project_id` - 项目数字 ID 的字符串形式，例如 `"6368"`（必填）
- `search` - 代码搜索关键词（必填）
- `page` / `per_page` - 分页（默认 1 / 20）

返回字段：`totalCount`、`page`、`pageSize`、`codeSnippets[]`；其中每个 `codeSnippets` 项包含 `fileName`、`filePath`、`commitId`、`projectId`、`fullName`、`fullPath`、`blobPath` 以及 `codeLines[]`（命中行：`lineNumber`、`preview`、`previewLength`、`offsetAndLengths`）

---

## create_repository

新建工蜂项目（Git 仓库）。

```
mcporter call gongfeng.create_repository name="<project-name>" [description="<desc>"] [visibility_level=<0|10>]
```

- `name` - 项目名称（必填）
- `description` - 项目描述（可选）
- `visibility_level` - 可见性级别（可选）：`0`=私有（private），`10`=内部（internal，仅登录用户可见）
- `namespace_id` - 命名空间 ID（可选），用于指定项目所属的命名空间（用户或组），可通过 `search_namespaces` 查询
- `create_from_id` - 模板项目 ID 或项目全路径（可选），用于基于已有项目/模板创建新仓库。传入项目全路径时需进行 encodeURIComponent 编码，`/` 转换为 `%2F`，请求示例：`root%2Fsubgroup01` (root/subgroup01)

---

## search_namespaces

搜索命名空间，查询所有匹配用户名称或路径的命名空间。

```
mcporter call gongfeng.search_namespaces [search="<keyword>"] [page=1] [per_page=10]
```

- `search` - 按名称或路径搜索命名空间（可选）
- `page` / `per_page` - 分页（默认 1 / 10）

返回字段：`id`, `name`, `path`, `kind`（`user` 或 `group`）等

---

## get_repository_tree

获取仓库目录树。

```
mcporter call gongfeng.get_repository_tree project_id="<id|path>" [ref_name="<branch>"] [path="<dir>"] [max_depth=1] [page=1] [per_page=10]
```

- `ref_name` - 分支/tag/commit，默认默认分支
- `path` - 子目录路径（可选）
- `max_depth` - 遍历深度，-1 不限制，默认 1

---

## get_project_detail

获取项目详细信息（含 full_path、web_url 等完整元数据）。

```
mcporter call gongfeng.get_project_detail project_id="<id|path>"
```

- 通过数字 ID 获取 full_path，或通过 full_path 获取数字 ID，二者均可
- 返回字段包含：`id`, `name`, `path_with_namespace`（full_path）, `description`, `web_url`, `created_at` 等

---

## get_project_members

列出项目成员；可选是否包含继承/共享组等成员。

```
mcporter call gongfeng.get_project_members \
  project_id="<id|path>" \
  [query="<keyword>"] \
  [include_inherited=false] \
  [page=1] [per_page=10]
```

- `include_inherited` - 默认 `false` 仅直接成员；`true` 时含祖先组继承、共享组与组织相关成员

---

## get_tapd_workitems

获取与 MR/Issue 关联的 TAPD 工作项。

```
mcporter call gongfeng.get_tapd_workitems project_id="<id|path>" type="mr"|"cr"|"issue" iid=<IID>
```

---

## create_label

在项目中创建新标签（对应项目 `/-/labels` 页面的标签管理）。

```
mcporter call gongfeng.create_label project_id="<id|path>" name="<label-name>" color="#FF0000"
```

- `name` - 标签名称（必填）
- `color` - 标签颜色，十六进制颜色码如 `#FF0000`

返回字段：`id`, `name`, `color`, `description`, `open_issues_count`, `closed_issues_count`, `open_merge_requests_count`, `priority`

---

## get_labels

获取项目所有标签（对应项目 `/-/labels` 页面的标签列表）。

```
mcporter call gongfeng.get_labels project_id="<id|path>" [type="project"] [include_ancestor_groups=false] [order_by="name"] [sort="asc"] [page=1] [per_page=20]
```

- `type` - 标签类型：`project`（项目标签）或 `review`（评审问题分类标签），默认 `project`
- `include_ancestor_groups` - 是否包含从父项目组继承的标签（默认 `false`）
- `order_by` - 排序字段：`name` 或 `created_at`（默认 `name`）
- `sort` - 排序方式：`asc` 或 `desc`（默认 `asc`）

返回字段：标签数组，每个标签包含 `id`, `name`, `color`, `description` 等

---

## create_milestone

在项目中创建新里程碑（对应项目 `/-/milestones` 页面的里程碑管理）。

```
mcporter call gongfeng.create_milestone project_id="<id|path>" title="<milestone-title>" [description="<desc>"] [due_date="yyyy-MM-dd"]
```

- `title` - 里程碑标题（必填）
- `description` - 里程碑描述（可选）
- `due_date` - 到期日期，格式 `yyyy-MM-dd`（可选）

返回字段：`id`, `iid`, `title`, `state`, `due_date`, `description`, `created_at`, `updated_at`

---

## get_milestones

获取项目所有里程碑（对应项目 `/-/milestones` 页面的里程碑列表）。

```
mcporter call gongfeng.get_milestones project_id="<id|path>" [iid=<iid>] [state="active"|"closed"] [order_by="created_at"] [sort="desc"] [page=1] [per_page=20]
```

- `iid` - 项目内里程碑序号，传入后仅返回该里程碑（可选）；传入后 state、order_by、sort、page、per_page 参数不生效
- `state` - 里程碑状态：`active`（进行中）或 `closed`（已关闭）
- `order_by` - 排序字段：`id`、`due_date`、`created_at`、`updated_at`（默认 `created_at`）
- `sort` - 排序方式：`asc` 或 `desc`（默认 `desc`）

返回字段：里程碑数组，每个里程碑包含 `id`, `iid`, `title`, `state`, `due_date`, `description`, `created_at`, `updated_at`



