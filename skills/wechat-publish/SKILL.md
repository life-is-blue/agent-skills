---
name: wechat-publish
description: Use when you need end-to-end WeChat publishing: dry-run preview, cover handling, draft creation/update, and publish status checks.
---

# WeChat Publisher — Execution Protocol

You are the **Publisher**，负责把 Markdown 文章安全地发到微信公众号草稿箱。

**核心契约**: 永远先 dry-run 确认 HTML 效果，再真实发布。发布后验证草稿存在。

## Quick Start

```bash
# 1. 安装依赖
bun add gray-matter sharp marked

# 2. 配置 .env
cat >> .env <<'EOF'
WECHAT_APPID=wx...
WECHAT_APPSECRET=...
WECHAT_AUTHOR=你的名字
EOF

# 3. 先 dry-run 确认效果
bun run publish article.md --dry-run

# 4. 确认无误后发布
bun run publish article.md --cover cover.webp
```

## Dependencies

| 包 | 用途 | 必须 |
|----|------|------|
| `gray-matter` | 解析 frontmatter | 是 |
| `sharp` | webp/gif → jpg 转换 + 压缩 | 是（macOS 可 fallback 到 sips） |
| `marked` | Alchemy 不可用时的本地 HTML 转换 | 建议 |

## Architecture

```
scripts/
├── wechat-api.ts       共享层: token、error、API wrappers
├── publish.ts          Markdown → 草稿（import wechat-api）
└── wechat-manage.ts    草稿管理 & 发布（import wechat-api）
```

发布流水线（publish.ts）:
```
  Markdown + frontmatter
         │
         ▼
  ┌─────────────┐    500?    ┌──────────┐
  │ Alchemy API │───────────▶│  marked   │
  │ (主题 HTML) │            │ (fallback)│
  └──────┬──────┘            └─────┬─────┘
         │                         │
         ▼                         ▼
     Themed HTML              Plain HTML
         │
    ┌────┴────┐
    │ 扫描图片 │
    └────┬────┘
         │
    ┌────┴──────────────────────────┐
    │  webp/gif → jpg (sharp)       │
    │  quality: 85→40, width≤1200   │
    └────┬──────────────────────────┘
         │
    ┌────┴────┐         ┌──────────────┐
    │uploadimg│         │add_material  │
    │(文章图) │         │(封面永久素材)│
    └────┬────┘         └──────┬───────┘
         │                     │
         ▼                     ▼
    ┌─────────────────────────────────┐
    │     /draft/add 创建草稿         │
    │  → media_id → 草稿箱验证       │
    └─────────────────────────────────┘
```

## Workflow

### Step 0: 封面图

微信草稿必须有封面图。**推荐做法：内嵌到文章 Markdown 中作为首张图片**。

#### 封面图内嵌规范

在 Markdown 的 `---`（frontmatter 之后的分隔线）下方、正文之前，插入封面图：

```markdown
---

![封面](./assets/NN-cover.webp)

正文第一段...
```

脚本自动检测 HTML 中首张 `<img>` 作为封面上传为永久素材，无需 `--cover` 参数。

#### 封面图生成

**方式 A: 手动准备** — 任何 jpg/png/webp 图片，建议 2.35:1 宽屏比例（900×383px）。

**方式 B: 用任意 AI 绘图工具生成** — 只要产物能导出为 jpg/png/webp 即可。

封面图命名规范：`NN-cover.webp`（如 `01-cover.webp`），系列总封面为 `00-series-cover.webp`。

生成后人工预览确认效果。

### Step 1: 发布前 Checklist

```
□ .env 有 WECHAT_APPID 和 WECHAT_APPSECRET
□ 公网 IP 在微信白名单中（curl ifconfig.me → mp.weixin.qq.com 添加）
□ 文章有 frontmatter（至少 title）
□ 封面图已内嵌为首张图片（![封面](./assets/NN-cover.webp)）
□ Markdown 原文 ≤7000 字（超过需 dry-run 检查 HTML chars）
□ 无残留占位符（<!-- ILLUSTRATION REQUEST --> 等）
□ 中英文标点统一（代码块内除外）
```

### Step 2: Dry-Run 预览

```bash
bun run publish <file.md> --dry-run
```

检查:
- 标题是否正确（≤32 字符，超长会被截断）
- **HTML chars ≤20000**（注意：CDN 图片 URL 比本地路径长 ~150 字符/张，实际发布会比 dry-run 多 ~400 chars）
- HTML 预览在浏览器中打开，确认排版和图片引用
- 图片列表是否完整（封面图应在列表首位）

### Step 3: 发布

确认 dry-run 无误后执行：

```bash
bun run publish <file.md> [options]
```

脚本会：
1. 解析 frontmatter（title, author, summary, source_url）
2. 调 Alchemy API 转 HTML（30s 超时）
3. 扫描本地图片，webp/gif 自动转 jpg（渐进降质，确保 ≤1MB）
4. 文章内图片用 `uploadimg`（不占素材配额），首图额外上传为封面素材
5. 校验 content 大小（≤2 万字符，≤1MB）
6. 创建草稿（默认开启评论）

### Step 4: 验证

发布成功后输出 `media_id`。去 mp.weixin.qq.com → 草稿箱 确认内容。

## CLI Reference

### publish.ts — 创建/更新草稿

```bash
bun run publish <markdown-file> \
  [--theme wechat-story] \
  [--title "标题"] \
  [--author "作者"] \
  [--cover cover.webp] \
  [--digest "摘要"] \
  [--source-url "https://..."] \
  [--update <media_id>] \
  [--dry-run]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<file>` | Markdown 文件路径 | 必填 |
| `--theme` | Alchemy 主题 ID | `wechat-story` |
| `--title` | 文章标题（≤32 字符） | frontmatter.title > 首个 `#` > 文件名 |
| `--author` | 作者（≤16 字符） | `WECHAT_AUTHOR` 环境变量 |
| `--cover` | 封面图路径 | HTML 中首张图片（推荐内嵌到 Markdown） |
| `--digest` | 摘要（≤128 字符） | frontmatter.summary > 标题 |
| `--source-url` | "阅读原文"链接 | frontmatter.source_url |
| `--update` | 覆盖已有草稿（传 media_id） | 不传则新建 |
| `--dry-run` | 只转 HTML 并打开预览 | - |

### wechat-manage.ts — 草稿管理 & 发布

```bash
# 列出所有草稿
bun run wechat draft list

# 删除草稿
bun run wechat draft delete <media_id>

# 覆盖已有草稿（等同 publish.ts --update）
bun run wechat draft update <media_id> <file.md>

# 提交发布（草稿 → 正式文章）
bun run wechat submit <media_id>

# 查询发布状态
bun run wechat status <publish_id>
```

典型流程: `publish.ts` 创建草稿 → `draft list` 确认 → 人工预览 → `submit` 提交发布 → `status` 查看结果。

> **更新 vs 删除重建**: 优先用 `--update` 覆盖草稿。定时发布中的草稿无法删除（error 53407），但可以用 `--update` 覆盖内容。

## Alchemy Format API（独立格式化）

除了通过 `publish.ts` 一键发布外，也可以单独使用 Alchemy API 将 Markdown 转换为微信 HTML。

### POST /api/format — Markdown → WeChat HTML

```bash
curl -X POST https://md.izoa.fun/api/format \
  -H "Content-Type: application/json" \
  -d '{
    "markdown": "# Hello World\n\nThis is a **demo** article.",
    "themeId": "wechat-story"
  }'
```

| Field       | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| markdown    | string | yes      | Markdown content to format               |
| themeId     | string | no       | Theme ID (default: `tencent-tech`)       |
| accentColor | string | no       | Hex color override, e.g. `#1a73e8`      |

### POST /api/ai — AI Text Processing

```bash
curl -X POST https://md.izoa.fun/api/ai \
  -H "Content-Type: application/json" \
  -d '{"text": "这是一段需要润色的文字", "action": "polish"}'
```

Actions: `polish` / `grammar` / `summarize` / `autoFormat` / `emphasize`

### MCP Integration

```bash
claude mcp add alchemy-formatter --transport http https://md.izoa.fun/api/mcp
```

## Environment

```bash
# .env（必填）
WECHAT_APPID=wx...
WECHAT_APPSECRET=...

# 可选
WECHAT_AUTHOR=Boris
ALCHEMY_API_URL=https://md.izoa.fun
WECHAT_API_BASE=https://wx.xxx.xyz/cgi-bin  # API 代理（国内直连不通时使用，建议换成自己的代理）
```

> **API 代理说明**: 如果网络无法直连 `api.weixin.qq.com`，配置 `WECHAT_API_BASE` 指向代理。
> 代理用 Caddy 反向代理到 `api.weixin.qq.com`，仅转发 `/cgi-bin/*` 路径。

## Design Principles

1. **Dry-Run First**: 永远先预览再发布。`--dry-run` 写本地 HTML 并自动打开
2. **不浪费配额**: 文章内图片用 `uploadimg`（不占 10 万素材上限），只有封面走永久素材
3. **格式透明转换**: webp/gif 自动转 jpg（微信 uploadimg 只收 jpg/png，且 ≤1MB）
   - 为什么不转 png？因为 webp→png 体积会膨胀（1.2MB webp → 1.4MB png，超 1MB 限制）
   - jpg 渐进降质：quality 85→40，步长 10，直到 ≤1MB
4. **Stable Token**: 用 `/cgi-bin/stable_token` 而非基础版，和公众号后台互相隔离
5. **Frontmatter 驱动**: 标题、摘要、原文链接都从 frontmatter 读取，CLI 参数覆盖
6. **封面图内嵌**: 封面图内嵌到 Markdown 作为首张图片，脚本自动检测。不再需要 `--cover` 参数（仍保留用于覆盖）

## Image Upload Strategy

微信有两种图片上传接口，用途不同：

| 接口 | 用途 | 配额影响 | 格式限制 |
|------|------|---------|---------|
| `/media/uploadimg` | 文章内图片 | **不占**素材配额 | jpg/png ≤1MB |
| `/material/add_material` | 封面图（永久素材） | 占用 10 万上限 | jpg/png/gif ≤10MB |

脚本自动处理：文章内图用 uploadimg，首图额外上传为永久素材作封面。

## Anti-Patterns

- 不 dry-run 直接发布（可能标题截断、图片丢失、排版错乱）
- 所有图片都用 `add_material`（浪费永久素材配额）
- 手动拼 HTML 传给微信（应该走 Alchemy API 保证主题一致性）
- 忽略 content 大小限制（微信静默截断，不报错）
- 在没有封面图的情况下发布（会报错，必须有 thumb_media_id）
- 用文章内随机图片当封面（应该准备专门的 2.35:1 封面图，并内嵌为首张图片）
- 依赖 dry-run 的 chars 数作为最终大小（CDN URL 替换后会多 ~150 chars/张图片，3 张图约多 400 chars）
- Markdown 中留着 `<!-- ILLUSTRATION REQUEST -->` 等注释就发布（脚本已自动 strip，但写文章时应在发布前清理占位符）
- 假设 Markdown 字数 ≈ HTML 字数（Alchemy inline styles 膨胀 2-3 倍，7000 字 Markdown 可能产出 20000+ chars HTML）

## Error Recovery

| 错误 | 原因 | 解决 |
|------|------|------|
| Alchemy API 500 | Vercel 服务端不可用 | 脚本自动 fallback 到本地 marked（无主题样式） |
| 40164 IP不在白名单 | 公网 IP 变了 | `curl ifconfig.me` 查 IP → mp.weixin.qq.com 添加白名单 |
| 40001/40125 凭证错误 | AppID/Secret 不对 | 检查 `.env` |
| 42001 token 过期 | 自动重试一次 | 脚本已内置 |
| 45009 配额用完 | 今日 API 次数耗尽 | 明天再试 |
| 图片转换失败 | sharp 未安装 | `bun add sharp` 或确保 macOS `sips` 可用 |
| webp 图片超 1MB | webp→png 体积膨胀 | 已改为 webp→jpg + 渐进降质，无需手动处理 |

## Available Themes

| ID | 风格 |
|----|------|
| `wechat-story` | 绿色，衬线体，文艺（默认） |
| `tencent-tech` | 蓝色，技术文档 |
| `github` | 开发者熟悉风格 |
| `classic-song` | 暖色，宋体，传统中文 |
| `history-book` | 红色，楷体，古典中文 |
| `google-clean` | 蓝色，Material Design |
| `magazine-elegant` | 紫色，杂志质感 |
| `zen-tea` | 青绿，极简禅意 |
| `focus-dark` | 深色背景，高对比度 |
| `gemini-docs` | Google Gemini 风格 |

## Pitfalls & Lessons

> 实际发布过程中踩过的坑，已在脚本中修复。

| 问题 | 原因 | 解决 |
|------|------|------|
| webp 图片上传失败 | uploadimg 只收 jpg/png，webp→png 后体积超 1MB | 改为 webp→jpg + 渐进降质（85→40） |
| Alchemy API 500 | Vercel Serverless 冷启动或服务异常 | 加了 fallback 到本地 `marked`（无主题样式但不阻塞发布） |
| IP 不在白名单 | 家庭网络公网 IP 会变化 | 发布前 `curl ifconfig.me` 确认，加到 mp.weixin.qq.com 白名单 |
| .env 变量找不到 | Bun 自动加载根目录 .env，但变量名必须精确 | 用 `WECHAT_APPID` 而非 `WX_APPID` 或其他变体 |
| 封面图 webp 上传 | add_material 接口同样不收 webp | 封面图也走 sharp 转换，但限制宽松（10MB） |
| HTML 注释吃字符 | `<!-- ILLUSTRATION REQUEST -->` 等注释被 Alchemy 原样保留到 HTML，计入 20000 字符限制 | 脚本已自动 strip HTML comments（`<!--...-->`） |
| 长文超 20000 限制 | Alchemy 的 inline styles 让 HTML 字符数膨胀约 2-3 倍（原文 ~9000 字 → HTML ~22000 chars） | 拆分上下篇。经验法则：**Markdown 原文超 7000 字就要警惕**，dry-run 看 chars |
| API 直连不通 | 国内/部分网络无法直连 api.weixin.qq.com | 配置 `WECHAT_API_BASE` 指向 Caddy 反向代理 |
| 定时发布不可用 | `freepublish/submit` 只能立即发布，`mass/sendall` 定时群发需认证公众号 | 非认证账号只能手动在公众号后台定时群发（支持 7 天内） |
| 定时发布中无法删除 | error 53407：「定时发布中，无法删除或修改」 | 用 `--update` 覆盖内容，或等发布完成/取消后再删 |
| dry-run 字符数 vs 实际字符数 | 本地路径 `./assets/xx.webp` 替换为 CDN URL `http://mmbiz.qpic.cn/...`（~150 chars/张） | dry-run 显示 19600 chars 但实际可能 20000+。**留 500 chars 余量** |
| 长文压缩超限 | 03 篇 Markdown 9000+ 字 → HTML 20331 chars | 压缩冗余表达（不删信息），目标 dry-run ≤19600 chars |

## Batch Publishing

```bash
# 1. 批量 dry-run（封面图已内嵌到各篇 Markdown，无需 --cover）
for f in knowledge/topics/<topic>/0[1-4]*.md; do
  bun run publish "$f" --dry-run
done

# 2. 确认预览无误后去掉 --dry-run
for f in knowledge/topics/<topic>/0[1-4]*.md; do
  bun run publish "$f"
done

# 3. 验证草稿箱
bun run wechat draft list
```

## Publishing Checklist（快速参考）

发布一篇文章的完整步骤：

```
1. 确认封面图已内嵌        grep '!\[封面\]' article.md
2. dry-run 检查大小         bun run publish article.md --dry-run
   → chars ≤19600?（留 400 余量给 CDN URL）
   → 图片列表完整？封面在首位？
3. 发布到草稿箱             bun run publish article.md
4. 验证草稿                 bun run wechat draft list
5. 人工预览                 mp.weixin.qq.com → 草稿箱 → 预览
6. 定时群发                 公众号后台手动设置（API 不支持非认证号定时）
```

更新已有草稿：

```
1. 获取 media_id            bun run wechat draft list
2. 覆盖草稿                 bun run publish article.md --update <media_id>
   或                       bun run wechat draft update <media_id> article.md
```

### 文章超限处理

当 dry-run 显示 chars > 19600：

1. **优先拆分**：上下篇各自独立 frontmatter，封面图共用（如 `04-cover.webp`）
2. **压缩表达**：删冗余修饰、合并相似段落、缩短类比。**保留信息量，只压缩表达方式**
3. **逐轮验证**：每轮压缩后 dry-run 确认，因为 CDN URL 膨胀会吃掉看似足够的余量
