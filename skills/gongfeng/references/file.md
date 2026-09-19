# File Handler — 文件操作（gongfeng）

## get_blob_content

获取文件的纯文本内容，支持 `start_line` / `end_line` 行范围裁剪；推荐用于获取源代码或文本文件。

```
mcporter call gongfeng.get_blob_content \
  project_id="<id|path>" \
  sha="<commit-sha|branch|tag>" \
  file_path="<path/to/file>" \
  [start_line=1] \
  [end_line=100]
```

- `sha` 支持 commit hash、分支名或 tag
- `start_line` / `end_line` 可截取行范围

---

## get_file_base64_content

下载文件内容（base64 编码）；单文件上限 20MB，超限报错。

> ⚠️ 本工具用于下载文件的 base64 内容，体积大、易挤爆上下文；请勿用该工具直接获取大文件结果（几 MB 也可能挤爆）。获取代码/文本请使用 `get_blob_content`。

```
mcporter call gongfeng.get_file_base64_content \
  project_id="<id|path>" \
  sha="<commit-sha|branch|tag>" \
  file_path="<path/to/file>" \
  [offset=0] \
  [length=8192]
```

- `sha` - commit hash、分支名或 tag
- `file_path` - 文件路径
- `offset` - base64 内容分片的起始字符偏移（从 0 开始），不传则从 0 开始
- `length` - 本次返回的 base64 最大字符数，不传则返回从 `offset` 起的所有剩余内容

返回分片字段：`content`（本片 base64）、`offset`、`length`、`total_size`（原始文件字节数）、`total_base64_length`（base64 总字符数）、`has_more`。当 `has_more` 为 true 时，用 `offset + length` 作为下一次的 `offset` 继续拉取，将各片 `content` 按序拼接后再整体 base64 解码即可还原完整文件。

---

## create_or_update_file

创建或更新单个文件（单文件提交）。支持两种互斥模式：
- **全量写入模式**：传入 `content`，创建或覆盖整个文件；配合 `encoding=base64` 可上传二进制文件
- **局部替换模式**：传入 `replacements`，服务端完成 get → edit → commit，无需传输整个文件，节省 token；二进制文件会被拒绝

```
# 全量写入模式（文本）
mcporter call gongfeng.create_or_update_file \
  project_id="<id|path>" \
  file_path="<path/to/file>" \
  content="<文件完整内容>" \
  commit_message="<提交信息>" \
  branch_name="<branch>"

# 全量写入模式（二进制，base64）
mcporter call gongfeng.create_or_update_file \
  project_id="<id|path>" \
  file_path="<path/to/binary>" \
  content="<base64编码内容>" \
  commit_message="<提交信息>" \
  branch_name="<branch>" \
  encoding="base64"

# 局部替换模式
mcporter call gongfeng.create_or_update_file \
  project_id="<id|path>" \
  file_path="<path/to/file>" \
  branch_name="<branch>" \
  commit_message="<提交信息>" \
  replacements='[{"search":"old text","replace":"new text"}]' \
  [dry_run=true]
```

### replacements 数组每项参数（局部替换模式）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 否 | `literal`（默认，精确匹配）或 `regex`（正则） |
| `search` | string | 是 | literal：要匹配的原始字符串；regex：正则表达式（不含首尾 `/`） |
| `replace` | string | 是 | 替换内容；regex 模式支持 `$1`、`$2` 反向引用 |
| `flags` | string | 否 | regex 模式的标志，如 `g`、`m`、`i`、`s`；literal 模式忽略 |
| `replace_all` | boolean | 否 | literal 模式下替换所有出现位置（默认 `false`，仅替换第一个匹配项） |
| `expected_count` | number | 否 | 预期匹配次数，不符则失败（安全校验） |

> ✅ 推荐：只需修改文件中少量代码时优先使用局部替换模式（`replacements`），避免传输整个文件内容

---

## batch_modify_files

批量修改文件（增/改/删，单次提交）。

```
mcporter call gongfeng.batch_modify_files \
  project_id="<id|path>" \
  branch_name="<branch>" \
  commit_message="<提交信息>" \
  [add_files='[{"path":"src/new.ts","content":"..."}]'] \
  [edit_files='[{"path":"src/old.ts","content":"..."}]'] \
  [delete_path='["src/remove.ts"]'] \
  [encoding="text"]
```

- `add_files` - 新增文件列表，每项含 `path` 和 `content`
- `edit_files` - 修改文件列表，每项含 `path` 和 `content`
- `delete_path` - 删除文件路径数组
- `encoding` - 内容编码方式：`base64`（`add_files`/`edit_files` 中的 `content` 为 base64 编码，用于二进制文件上传）或 `text`（纯文本，默认）

> ✅ 推荐：多文件变更用 `batch_modify_files` 合并为单次提交，避免多次调用 `create_or_update_file`

---

## get_file_blame

获取文件 blame/历史信息（逐行作者）。

```
mcporter call gongfeng.get_file_blame \
  project_id="<id|path>" \
  file_path="<path/to/file>" \
  [ref="<branch|tag|commit>"] \
  [line_number=<N>] \
  [start_line=<M>] \
  [end_line=<N>]
```

- `line_number` - 查询特定行
- `start_line` / `end_line` - 查询行范围（优先于 `line_number`）

---


