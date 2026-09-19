# User Handler — 用户信息（gongfeng）

## get_current_user

获取当前登录用户信息。

```
mcporter call gongfeng.get_current_user
```

返回当前 token 对应的用户基本信息（用户名、邮箱、ID 等）。

---

## get_user_info

按 ID 或用户名查询用户信息。

```
mcporter call gongfeng.get_user_info user_id="<userId-or-username>"
```

- `user_id` 为 **字符串**（schema：`string`）；数字 ID 请写成字符串，如 `"12345"`，也可传英文 `username`

---

## get_user_events

获取当前登录用户的事件动态列表（推送、合并、评论、团队变动、Wiki 推送、SVN 提交等）。

```
mcporter call gongfeng.get_user_events
mcporter call gongfeng.get_user_events event_filter="push,merged" per_page=10
```

- `begin_date`（可选 string）：事件起始时间，ISO 8601 格式，时间参数中的 `+` 必须转码为 `%2B`。默认值为 end_date 往前一个月
- `end_date`（可选 string）：事件结束时间，ISO 8601 格式，时间参数中的 `+` 必须转码为 `%2B`。默认值为当前时间
- `event_filter`（可选 string）：事件类型过滤，多个类型用英文逗号分隔。可选值：`push`、`merged`、`comments`、`team`、`wikiPush`、`svnCommit`
- `page`（可选 number）：页数（默认值：1）
- `per_page`（可选 number）：每页数量（默认值：20，最大值：100）

返回当前用户的事件动态数组。
