# Review Rule Handler — 评审规则（gongfeng）

## get_review_rule_config

查询指定项目关联的规则集列表及项目配置的规则文件搜索路径。

```
mcporter call gongfeng.get_review_rule_config project_id="<id|path>"
```

- `project_id` - 项目 ID 或项目完整路径（必填）

返回字段：
- `rule_sets` - 规则集列表（最多 1 条），每项包含：`id`, `biz_space`, `rule_set_name`, `visibility`（1=公开，2=私有）, `rule_count`
- `rule_paths` - 项目配置的规则文件搜索路径列表，如 `.cursorrules`、`.codebuddy/rules/*`

---

## get_review_rules_by_files

查询指定规则集下，与文件路径匹配的评审规则列表。

```
mcporter call gongfeng.get_review_rules_by_files project_id="<id|path>" rule_set_id=<id> file_paths='["src/a.js","src/b.ts"]'
```

- `project_id` - 项目 ID 或项目完整路径（必填）
- `rule_set_id` - 规则集 ID（必填），必须属于当前项目，否则返回 404
- `file_paths` - 文件路径列表（必填），用于匹配对应规则集下对这些文件生效的评审规则

返回规则数组，每项包含：`id`, `rule_set_id`, `biz_space`, `title`, `description`, `category`, `defect_level`（1=提示，2=警告，3=错误）, `rule_url`, `effective_condition`, `effective_condition_value_list`, `negative_samples`, `positive_samples`, `creator_id`

---

## get_review_rule_detail

查询指定规则集下单条已发布规则的详细信息。

```
mcporter call gongfeng.get_review_rule_detail project_id="<id|path>" rule_set_id=<id> rule_id=<id>
```

- `project_id` - 项目 ID 或项目完整路径（必填）
- `rule_set_id` - 规则集 ID（必填），必须属于当前项目，否则返回 404
- `rule_id` - 规则 ID（必填），必须属于该规则集，否则返回 400

返回单条规则对象，字段与 `get_review_rules_by_files` 列表中每项一致。
