# 官方文档与示例入口

按遇到的语义读取对应条目，不必每次加载全部文档。以下为官方来源索引，不是上游快照；字段与权限会变化，不以示例或旧本地校验器替代详细文档。可用已安装的文档检索工具找原文（例如 search-docs），也可直接访问链接；本技能不依赖额外 Skill 安装。

| 主题 | 官方来源与核对重点 |
|---|---|
| 迁移总览 | [GitHub Actions → CNB](https://docs.cnb.cool/zh/build/migrate-to-cnb/migrate-from-github-actions.html)：术语、runner、needs、matrix、cache、artifact。概念映射不是完整行为等价保证。 |
| YAML 与执行语义 | [Pipeline grammar](https://docs.cnb.cool/zh/build/grammar.html)：Pipeline/Stage/Job、lock 的秒单位、ifModify 适用事件、条件 OR 关系、include 与 imports。 |
| 事件与信任边界 | [Trigger rules](https://docs.cnb.cool/zh/build/trigger-rule.html)：tag 精确/glob/兜底匹配、PR 代码版本、不可信事件与外部引用限制。不把默认 token 限权等同于代码安全。 |
| 页面按钮 | [Web trigger](https://docs.cnb.cool/zh/build/web-trigger.html)：`branch[].buttons[]`、inputs 对象或分组、event 配对；按钮 env 不可编辑，inputs 可编辑。页面 permissions 不是后端安全边界。 |
| 定时 | [CNB crontab](https://docs.cnb.cool/zh/build/crontab.html) 与 [GHA schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)：CNB 为 Asia/Shanghai、明确单分支、最小间隔 5min；源端读取实际 timezone（默认 UTC），检查日期和夏令时差异。 |
| 变量与输出 | [Environment variables](https://docs.cnb.cool/zh/build/env.html)：env/imports 优先级、变量替换和 exports 的 Pipeline 生命周期。配置插值不是 shell 参数展开。 |
| Commit 身份与令牌 | [Built-in env](https://docs.cnb.cool/zh/build/build-in-env.html)：CNB_BRANCH、CNB_COMMIT、CNB_PULL_REQUEST_MERGE_SHA、工作区和 CNB_TOKEN 的事件/仓库权限；PR 的事件 SHA 与 checkout 可能不同。 |
| 密钥 | [Secret store](https://docs.cnb.cool/zh/repo/secret.html) 与 [File reference](https://docs.cnb.cool/zh/build/file-reference.html)：imports、allow_* 的引用授权；include 只引用配置，不能直接引用密钥仓文件。创建/修改密钥和引用权限是独立受批操作。 |
| 缓存 | [Pipeline cache](https://docs.cnb.cool/zh/build/pipeline-cache.html)：节点 volume 与跨节点 docker:cache；缓存命中不作正确性依赖，不以默认镜像缓存替代 actions/cache。 |
| 超时 | [Timeout strategy](https://docs.cnb.cool/zh/build/timeout.html)：Pipeline 最长 20h；Job 默认总时限 2h、无输出 10min。显式 timeout 同时设置这两者，Job 上限 12h；配置用带单位值，不自动增加业务重构。 |
| 内置任务 | [Internal steps](https://docs.cnb.cool/zh/build/internal-steps.html)：await/resolve 依赖同步；git:release 的 options 包括 tag/title/description/descriptionFromFile/preRelease/latest/overlying。非 tag_push 需明确 tag；默认 overlying=false 会删后重建已有 Release，不能当无害重试。target_commitish 不是此任务字段；直调 API 时另查所用 endpoint，不假定必填。 |
| 附件插件 | [Attachments README](https://cnb.cool/cnb/plugins/market/-/git/raw/main/plugins/cnbcool/attachments/README.md)：支持事件、UPLOAD/DOWNLOAD、tag/commit、路径/文件名与 ttl。tag_push 默认操作 Tag 对应 Release，Release 必须先存在；其他事件默认 commit 附件。核对源 workflow 的消费者，而非只改上传步骤。 |

## 骨架使用边界

[example.cnb.yml](example.cnb.yml) 展示共享构建步骤，以及同 Pipeline 内「构建 → 检查产物 → 创建 Release → 上传附件」的顺序。写入共用 Stage 门禁，默认禁用；没有密钥依赖，只有真实需要时才加入 imports。

使用时替换全部占位符并裁剪无关事件。main、tag 匹配、时限、产物路径与发布目标都必须来自实际需求。迁移到 CNB 执行不等于发布目标也迁到 CNB：若仍发布到 GitHub，不使用此处的 CNB Release 片段替代它。示例中的互斥锁保留运行，不默认取消上一个发布；不同并发要求需按源语义调整。

## 手动验证入口（按需）

仅当源 workflow 有手动入口或请求需要时，将下列配置放入目标仓库 `.cnb/web_trigger.yml`。它对应骨架的 `main.web_trigger_verify`，不发布，不必引入 DRY_RUN 参数。

```yaml
branch:
  - reg: ^main$
    buttons:
      - name: 验证构建
        event: web_trigger_verify
```

有原始 workflow_dispatch 参数时，在对应按钮下按原名/类型/默认值添加 `inputs`。例如下列字段适用于**另行配置并验证好写入门禁**的手动发布入口，不要仅把按钮指向验证流水线就认为它能发布：

```yaml
inputs:
  DRY_RUN:
    name: 只验证，不发布
    type: select
    default: "1"
    options:
      - name: 只验证
        value: "1"
      - name: 执行已授权发布
        value: "0"
```

不要在按钮 env 或流水线 env 再固定同名参数；在 shell 中处理缺省/非法值，确认输入确实抵达门禁。页面可选项不是授权，后端仍需控制事件、代码与凭据边界。手动 Release 还需明确 tag 并核对附件插件是否支持该事件，不能原样搬用 tag_push 的默认值。

## 本地校验与远程取证

可用 [Pipeline JSON Schema](https://docs.cnb.cool/conf-schema-zh.json) 和 [Web-trigger JSON Schema](https://docs.cnb.cool/web-trigger-schema-zh.json) 辅助检查字段；Schema 不证明依赖正确或副作用被隔离。适配 CNB 扩展语法后再校验；不要为了通过过期客户端规则擅自改成错误的事件语义。

CLI 以本机帮助和最小只读查询为准。接口入口为 [CNB OpenAPI](https://api.cnb.cool/)；确认具体 endpoint、参数和返回结构后，读取目标构建状态和失败阶段完整日志。没有认证/网络时明确记录远程未验，不新增 token 或无限重试，也不要求本地改动必须先产生构建 SN。
