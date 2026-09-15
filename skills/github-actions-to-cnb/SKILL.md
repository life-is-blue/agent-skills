---
name: github-actions-to-cnb
description: "将仓库的 GitHub Actions workflow（.github/workflows/*.yml）迁移为 CNB（Cloud Native Build，cnb.cool）流水线（.cnb.yml / .cnb/web_trigger.yml）。给出六阶段迁移流程（Inventory/Classify/Map/Secrets/Dry-run/Dual-track cutover）、GitHub Actions 到 CNB 的原语映射表（schedule/workflow_dispatch/push.paths/concurrency/matrix/cache/artifact/secrets/token）、runner 系统依赖基线，以及证据化排障命令。触发词：GitHub Actions 迁移 CNB、迁移到 CNB、.cnb.yml、web_trigger、CNB 流水线、GHA to CNB、cnb.cool migration。"
---

# GitHub Actions → CNB 迁移

把一个仓库的 GitHub Actions workflow 迁移为 CNB `.cnb.yml` 流水线。目标平台专属：不适用于迁到其他 CI（不同平台的原语不通用）。

## 核心原则

1. **不删旧的**：迁移期间 `.github/workflows/` 保留不动。回滚 = 重新打开触发器，不是代码回退。
2. **先只读不写**：第一轮先跑通 dry-run（`DRY_RUN=1` 或等价开关），只验证 install/build/test 链路，不碰 deploy/release。
3. **一个开关管一件事**：`env` 放不可编辑默认值，页面可编辑参数放 `inputs`；两者同名会导致该参数在 CNB 页面上渲染成不可编辑，形同虚设。
4. **证据优先**：每次改动后必须能给出 build SN + 失败 stage 的日志行，不能凭感觉判断"应该好了"。

## Preflight

```bash
test -d .github/workflows && ls .github/workflows/*.yml
command -v cnb >/dev/null 2>&1 || echo "no cnb CLI: 用 curl + \$CNB_TOKEN 走 OpenAPI 取证据"
```

## 六阶段流程

### 1. Inventory（盘点）

逐个读 `.github/workflows/*.yml`，记录：

- 触发方式：`schedule.cron` / `workflow_dispatch` / `push.paths` / `pull_request`
- 并发控制：`concurrency.group` + `cancel-in-progress`
- 密钥：`secrets.*` / `vars.*`，记键名和使用位置
- 产物链路：`actions/upload-artifact` 是否被下游 job 消费；是否创建 GitHub Release
- 平台专有依赖：`github.token`、`GITHUB_STEP_SUMMARY`、`GITHUB_REF_NAME`/`GITHUB_SHA`、`gh` CLI

### 2. Classify（分层）

把每个 workflow 归到一类，决定迁移顺序：

| 类型 | 迁移优先级 | 理由 |
|---|---|---|
| 数据/计算构建（跑测试、生成产物） | 优先 | 风险低，收益直接 |
| PR/push 质量门禁（check/lint） | 次优先 | 省 GitHub Actions 分钟数 |
| 发布链路（多平台 matrix、npm publish 等） | 默认暂不迁 | matrix 改造成本高，出错直接影响用户 |

### 3. Map（映射）

逐条对照下表，把每个 GitHub Actions 原语落到 `.cnb.yml` 草稿：

| GitHub Actions | CNB | 备注 |
|---|---|---|
| `schedule.cron` | 顶层事件 `"crontab: <cron 表达式>"` | 最小调度间隔通常 5 分钟 |
| `workflow_dispatch`（+ `inputs`） | `.cnb/web_trigger.yml` 的 `buttons[].inputs` | 页面可编辑参数只能放 `inputs`，不能放 `env` |
| `push.paths` | `ifModify` | 可配在 pipeline/stage/job 级 |
| `concurrency.group` + `cancel-in-progress` | `lock.key` + `cancel-in-progress` / `cancel-in-wait` | 可做互斥或排队抢占 |
| `strategy.matrix` | 无原生 matrix | 用 YAML 锚点（`&anchor` / `<<: *anchor`）复制多份，或改成单 pipeline 顺序 stage |
| `actions/cache` | docker 镜像自带缓存 + CNB 内置节点缓存 | 无需手工声明 cache key |
| `actions/upload-artifact` + 下游消费 | `cnbcool/attachments:latest`，或直接用 CNB Release + 附件 | |
| `secrets.*` / `vars.*` | 私有 `imports` 密钥仓 + `env` 块读取 | 见下方 Secrets |
| `github.token` / `gh` CLI | 内置 `CNB_TOKEN`（可信事件下自动注入） | 部署令牌只读，不能建 release |
| `GITHUB_STEP_SUMMARY` | 无直接对应 | 改为脚本 `echo` 到标准输出，靠日志排障 |
| `GITHUB_REF_NAME` / `GITHUB_SHA` | `CNB_BRANCH` / `CNB_BRANCH_SHA` | 过渡期可在脚本里做变量兼容映射 |

Runner 依赖基线（几乎每个迁移都需要；缺一项通常在 `install` 阶段才报错）：

```yaml
- name: install-system-deps
  script: |
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        git ca-certificates openssh-client rsync curl jq
      rm -rf /var/lib/apt/lists/*
    elif command -v apk >/dev/null 2>&1; then
      apk add --no-cache git ca-certificates openssh-client rsync curl jq
    else
      echo "Unsupported package manager: need apt-get or apk" >&2
      exit 1
    fi
```

按实际脚本裁剪包列表；`rsync` 最容易被漏掉（往往要等 deploy 阶段用 worktree 同步时才报错）。

### 4. Secrets（密钥映射）

1. 不把密钥写进 `.cnb.yml` 或提交历史。用 `imports` 指向受控的私有密钥仓库文件。
2. 建一张映射表：GitHub 密钥名 → CNB 密钥仓键名 → 注入后环境变量名 → 使用位置。逐条核对，不留遗漏。
3. 含密钥的 `imports` 只放受控仓库；业务仓库通过 `include` 引用，不直接内联敏感内容。

### 5. Dry-run（先跑通逻辑，不动生产）

1. 先用页面按钮触发（`web_trigger`），`DRY_RUN=1`：只验证 install/build/test 链路，跳过 deploy/release。
2. 连续拿到 3 次成功的 build SN 再进入下一阶段——一次绿不算数。
3. 不可信事件（PR / 评论触发）不得跑到带写权限的 stage。

### 6. Dual-track → Cutover（双轨切流）

1. 阶段 A：GitHub Actions 照常跑；CNB 只手动 / dry-run。
2. 阶段 B：CNB 开 `crontab`，仍 `DRY_RUN=1`，观察稳定性。
3. 阶段 C：CNB `DRY_RUN=0`；同时**注释掉**（不是删除）GitHub workflow 里的 `schedule`，保留 `workflow_dispatch` 作为回滚入口。
4. 切流当天只改触发器，不改业务脚本——回滚永远是分钟级的开关翻转，不是代码回退。

## 验证证据（每次改动后过一遍）

1. 触发是否生效（按钮 / 定时 / push）。
2. 写入是否生效（目标分支是否有新提交）。
3. 发布是否生效（Release 是否有资产；`target_commitish` 等必填字段是否补全）。
4. 运行时是否可读（下游消费方能否按新链路拉到产物）。

查证据用 CNB OpenAPI，不要只看页面颜色：

```bash
# 最近构建
cnb build get-build-logs --path '{"repo":"<org>/<repo>"}' --query '{"page":1,"page_size":5}'
# 某次构建的 stage 状态
cnb build get-build-status --path '{"repo":"<org>/<repo>","sn":"<SN>"}'
# 失败 stage 的完整日志（CLI 展示可能截断，改用 OpenAPI 直拉）
curl -sS -H "Authorization: Bearer $CNB_TOKEN" -H "Accept: application/vnd.cnb.api+json" \
  "https://api.cnb.cool/<org>/<repo>/-/build/logs/stage/<SN>/<pipeline-id>/<stage-id>" | jq -r '.content[]'
```

只根据"最后一个失败点"改动，一轮只改一处根因，改完立刻复验。

## Anti-Patterns

- 删除或改写 `.github/workflows/`——迁移期只加 CNB 配置，不动旧配置；回滚要靠开关，不是靠 git revert。
- 同一个变量既放 `env` 又放 `inputs`——CNB 页面会把它渲染成不可编辑，参数形同虚设。
- 把 `strategy.matrix` 硬套 CNB——CNB 没有原生 matrix，生搬会写出一堆重复 stage；要么用 YAML 锚点复用，要么改成单 pipeline 顺序执行。
- 密钥直接写进 `.cnb.yml` 或提交历史——一律走密钥仓库 `imports`。
- 没有连续 dry-run 成功记录就直接 `DRY_RUN=0` 切流。
- 日志被截断时靠猜——用 `get-build-stage` / OpenAPI 拿完整内容，从尾部往前看（错误通常在最后几行）。
- 不可信事件（PR / 评论触发）跑到带写权限的 stage。

## 何时不适用

- 目标平台不是 CNB（不同 CI 有各自的原语，映射表不通用）。
- 只是想了解 CNB 本身——直接查 CNB 官方文档，不需要这份迁移协议。
- Workflow 里没有触发器 / 密钥 / 发布链路（纯静态文件）——直接手写 `.cnb.yml` 即可，不必走六阶段流程。
