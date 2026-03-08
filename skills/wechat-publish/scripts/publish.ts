#!/usr/bin/env bun
/**
 * publish.ts — 微信公众号草稿发布
 *
 * Markdown → Alchemy API 转 HTML → 上传图片 → 创建草稿
 *
 * 图片上传策略:
 *   - 文章内图片: /cgi-bin/media/uploadimg（不占素材配额，仅 jpg/png ≤1MB）
 *   - 封面图: /cgi-bin/material/add_material（永久素材，草稿 API 要求）
 *   - webp/gif → jpg 自动转换 + 渐进降质（85→40），确保 ≤1MB
 *
 * HTML 转换:
 *   - 优先 Alchemy API（带主题样式），失败时 fallback 到本地 marked（无样式）
 *
 * Token 策略: 使用 /cgi-bin/stable_token（和基础版隔离，不互踩）
 *
 * 踩坑记录:
 *   - webp→png 会导致体积膨胀（1.2MB webp → 1.4MB png），改用 jpg + 降质
 *   - Alchemy API 部署在 Vercel，偶尔 500，需要 fallback
 *   - 微信 IP 白名单：家庭网络公网 IP 会变，发布前 curl ifconfig.me 确认
 *   - Bun 自动加载 .env，但变量名必须精确匹配（WECHAT_APPID，非 WX_APPID）
 */

import { resolve, dirname, basename, extname } from "path";
import { readFileSync, existsSync, writeFileSync, unlinkSync } from "fs";
// @ts-ignore — gray-matter CJS default export
import matter from "gray-matter";
import {
  WECHAT_API,
  LIMITS,
  DEFAULT_AUTHOR,
  getAccessToken,
  handleWeChatError,
  truncate,
  fmtBytes,
  apiDraftAdd,
  apiDraftUpdate,
} from "./wechat-api";

// ─── Config (local to publish) ───────────────────────────────────────────────

const ALCHEMY_API = process.env.ALCHEMY_API_URL || "https://md.izoa.fun";
const DEFAULT_THEME = "wechat-story";

// ─── WeChat API: Image Upload ────────────────────────────────────────────────

/**
 * 上传文章内图片（/cgi-bin/media/uploadimg）
 *
 * 不占公众号素材库的 10 万张配额。
 * 限制: 仅 jpg/png，≤1MB。webp/gif 需先转 png。
 * 返回: 微信 CDN URL（无 media_id）
 */
async function uploadArticleImage(imagePath: string): Promise<string> {
  const prepared = await prepareImage(imagePath, LIMITS.UPLOADIMG_BYTES);

  const token = await getAccessToken();
  const url = `${WECHAT_API}/media/uploadimg?access_token=${token}`;

  const form = new FormData();
  form.append(
    "media",
    new Blob([prepared.data as BlobPart], { type: prepared.mime }),
    prepared.filename
  );

  const res = await fetch(url, { method: "POST", body: form });
  const data = await res.json();

  handleWeChatError(data, `上传文章图片 ${prepared.filename}`);

  // 清理临时转换文件
  if (prepared.tempPath) cleanupTemp(prepared.tempPath);

  return data.url;
}

/**
 * 上传封面图（/cgi-bin/material/add_material）
 *
 * 草稿 API 要求 thumb_media_id 是永久素材。
 * 限制: jpg/png/gif，≤10MB。
 */
async function uploadCoverImage(
  imagePath: string
): Promise<{ mediaId: string; url: string }> {
  const prepared = await prepareImage(imagePath, LIMITS.MATERIAL_BYTES);

  const token = await getAccessToken();
  const url = `${WECHAT_API}/material/add_material?access_token=${token}&type=image`;

  const form = new FormData();
  form.append(
    "media",
    new Blob([prepared.data as BlobPart], { type: prepared.mime }),
    prepared.filename
  );

  const res = await fetch(url, { method: "POST", body: form });
  const data = await res.json();

  handleWeChatError(data, `上传封面 ${prepared.filename}`);

  if (prepared.tempPath) cleanupTemp(prepared.tempPath);

  return { mediaId: data.media_id, url: data.url || "" };
}

interface PreparedImage {
  data: Uint8Array;
  mime: string;
  filename: string;
  tempPath?: string; // 如果做了格式转换，临时文件路径
}

/**
 * 准备图片: 检查格式/大小，必要时转换
 *
 * uploadimg 只接受 jpg/png（≤1MB），不接受 webp/gif。
 * webp/gif 用 sharp 转 jpg（自动降质压到 1MB 以内）。
 *
 * 降质策略: width≤1200px，quality 从 85 递减到 40（步长 10）。
 * 实测 1.4MB webp → ~200KB jpg@85，完全够用。
 * fallback: macOS sips（无渐进降质，但能应急）。
 */
async function prepareImage(
  imagePath: string,
  maxBytes: number
): Promise<PreparedImage> {
  const absPath = resolve(imagePath);
  if (!existsSync(absPath)) throw new Error(`图片不存在: ${absPath}`);

  const ext = extname(absPath).toLowerCase();
  const fileData = readFileSync(absPath);

  // webp/gif → jpg 转换（jpg 比 png 体积小得多，适合 1MB 限制）
  if (ext === ".webp" || ext === ".gif") {
    const jpgPath = absPath.replace(/\.(webp|gif)$/i, ".tmp.jpg");

    // 用 sharp 转 jpg，限制宽度 1200px，quality 从 85 开始
    let converted = false;
    try {
      const sharp = (await import("sharp")).default;
      let quality = 85;
      while (quality >= 40) {
        await sharp(absPath)
          .resize({ width: 1200, withoutEnlargement: true })
          .jpeg({ quality })
          .toFile(jpgPath);
        const stat = Bun.file(jpgPath);
        if (stat.size <= maxBytes) {
          converted = true;
          break;
        }
        quality -= 10;
      }
    } catch {
      // fallback: sips（macOS 自带，不支持质量调节但能转格式）
      Bun.spawnSync({
        cmd: ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", absPath, "--out", jpgPath],
      });
      if (existsSync(jpgPath)) converted = true;
    }

    if (!converted || !existsSync(jpgPath)) {
      cleanupTemp(jpgPath);
      throw new Error(
        `无法转换 ${ext} → jpg。请安装 sharp (bun add sharp) 或确保 sips 可用`
      );
    }

    const jpgData = readFileSync(jpgPath);
    if (jpgData.length > maxBytes) {
      cleanupTemp(jpgPath);
      throw new Error(
        `转换后图片 ${basename(absPath)} 仍超过大小限制 (${fmtBytes(jpgData.length)} > ${fmtBytes(maxBytes)})，即使 quality=40`
      );
    }

    return {
      data: jpgData,
      mime: "image/jpeg",
      filename: basename(absPath, ext) + ".jpg",
      tempPath: jpgPath,
    };
  }

  // jpg/png 直接使用
  if (fileData.length > maxBytes) {
    throw new Error(
      `图片 ${basename(absPath)} 超过大小限制 (${fmtBytes(fileData.length)} > ${fmtBytes(maxBytes)})`
    );
  }

  const mimeMap: Record<string, string> = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
  };
  const mime = mimeMap[ext];
  if (!mime) {
    throw new Error(
      `不支持的图片格式: ${ext}。微信 uploadimg 仅支持 jpg/png`
    );
  }

  return { data: fileData, mime, filename: basename(absPath) };
}

function cleanupTemp(path: string): void {
  try {
    if (existsSync(path)) unlinkSync(path);
  } catch {
    // 静默忽略清理失败
  }
}

// ─── WeChat API: Draft ───────────────────────────────────────────────────────

interface WeChatArticle {
  title: string;
  content: string;
  author?: string;
  thumbMediaId: string;
  digest?: string;
  contentSourceUrl?: string;
}

async function createDraft(article: WeChatArticle): Promise<string> {
  // 校验 content 大小
  const contentChars = article.content.length;
  const contentBytes = Buffer.byteLength(article.content, "utf-8");

  if (contentChars > LIMITS.CONTENT_CHARS) {
    throw new Error(
      `文章内容超过微信限制: ${contentChars} 字符 (上限 ${LIMITS.CONTENT_CHARS})`
    );
  }
  if (contentBytes > LIMITS.CONTENT_BYTES) {
    throw new Error(
      `文章内容超过微信限制: ${fmtBytes(contentBytes)} (上限 ${fmtBytes(LIMITS.CONTENT_BYTES)})`
    );
  }

  return apiDraftAdd({
    articles: [
      {
        title: truncate(article.title, LIMITS.TITLE_CHARS),
        author: truncate(article.author || "", LIMITS.AUTHOR_CHARS),
        digest: truncate(
          article.digest || article.title,
          LIMITS.DIGEST_CHARS
        ),
        content: article.content,
        content_source_url: article.contentSourceUrl || "",
        thumb_media_id: article.thumbMediaId,
        show_cover_pic: 1,
        need_open_comment: 1,
        only_fans_can_comment: 0,
      },
    ],
  });
}

async function updateDraft(
  mediaId: string,
  article: WeChatArticle
): Promise<void> {
  const contentChars = article.content.length;
  const contentBytes = Buffer.byteLength(article.content, "utf-8");

  if (contentChars > LIMITS.CONTENT_CHARS) {
    throw new Error(
      `文章内容超过微信限制: ${contentChars} 字符 (上限 ${LIMITS.CONTENT_CHARS})`
    );
  }
  if (contentBytes > LIMITS.CONTENT_BYTES) {
    throw new Error(
      `文章内容超过微信限制: ${fmtBytes(contentBytes)} (上限 ${fmtBytes(LIMITS.CONTENT_BYTES)})`
    );
  }

  await apiDraftUpdate(mediaId, 0, {
    title: truncate(article.title, LIMITS.TITLE_CHARS),
    author: truncate(article.author || "", LIMITS.AUTHOR_CHARS),
    digest: truncate(article.digest || article.title, LIMITS.DIGEST_CHARS),
    content: article.content,
    content_source_url: article.contentSourceUrl || "",
    thumb_media_id: article.thumbMediaId,
    show_cover_pic: 1,
    need_open_comment: 1,
    only_fans_can_comment: 0,
  });
}

// ─── Alchemy API ─────────────────────────────────────────────────────────────

async function markdownToHtmlViaAlchemy(
  markdown: string,
  theme: string
): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const res = await fetch(`${ALCHEMY_API}/api/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, themeId: theme }),
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(`Alchemy API 错误: ${res.status} ${res.statusText}`);
    }

    const data = await res.json();
    if (!data.success) {
      throw new Error(`Alchemy API 返回失败: ${JSON.stringify(data)}`);
    }
    return data.html;
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Alchemy API 超时 (30s)。服务可能不可用。");
    }
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

async function markdownToHtmlLocal(markdown: string): Promise<string> {
  const { marked } = await import("marked");
  console.warn("  ⚠ Alchemy 不可用，使用本地 marked 转换（无主题样式）");
  return await marked(markdown);
}

async function markdownToHtml(
  markdown: string,
  theme: string
): Promise<string> {
  try {
    return await markdownToHtmlViaAlchemy(markdown, theme);
  } catch (e: any) {
    console.warn(`  ⚠ ${e.message}`);
    return await markdownToHtmlLocal(markdown);
  }
}

// ─── Image Processing ────────────────────────────────────────────────────────

interface ImageRef {
  original: string; // HTML 中的 src 值
  absPath: string; // 本地绝对路径
}

function findLocalImages(html: string, baseDir: string): ImageRef[] {
  const images: ImageRef[] = [];
  const regex = /<img[^>]+src=["']([^"']+)["'][^>]*>/gi;
  let match;

  while ((match = regex.exec(html)) !== null) {
    const src = match[1];
    if (src.startsWith("http://") || src.startsWith("https://")) continue;

    const absPath = resolve(baseDir, src);
    if (existsSync(absPath)) {
      images.push({ original: src, absPath });
    } else {
      console.log(`  [WARN] 图片不存在，跳过: ${src}`);
    }
  }

  return images;
}

/**
 * 上传文章内图片并替换 HTML 中的路径
 *
 * 使用 uploadimg（不占素材配额）。
 * 同时用 add_material 上传首图作为封面候选。
 */
async function uploadAndReplace(
  html: string,
  images: ImageRef[]
): Promise<{ html: string; coverMediaId: string }> {
  let result = html;
  let coverMediaId = "";

  for (let i = 0; i < images.length; i++) {
    const img = images[i];
    try {
      // 文章内图片: uploadimg（返回 URL，不占素材配额）
      const cdnUrl = await uploadArticleImage(img.absPath);
      console.log(`  ✓ ${basename(img.absPath)} → ${cdnUrl.slice(0, 60)}...`);

      result = result.split(img.original).join(cdnUrl);

      // 首图同时上传为永久素材作为封面候选
      if (i === 0 && !coverMediaId) {
        console.log(`  → 首图同时上传为封面素材...`);
        const { mediaId } = await uploadCoverImage(img.absPath);
        coverMediaId = mediaId;
      }
    } catch (e: any) {
      console.log(`  [WARN] 上传失败 ${basename(img.absPath)}: ${e.message}`);
    }
  }

  return { html: result, coverMediaId };
}


// ─── CLI ─────────────────────────────────────────────────────────────────────

interface CliOpts {
  file: string;
  theme: string;
  title?: string;
  author?: string;
  cover?: string;
  digest?: string;
  sourceUrl?: string;
  update?: string; // media_id to update instead of creating new draft
  dryRun: boolean;
}

function parseArgs(): CliOpts {
  const args = process.argv.slice(2);
  const opts: any = { theme: DEFAULT_THEME, dryRun: false };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--theme":
        opts.theme = args[++i];
        break;
      case "--title":
        opts.title = args[++i];
        break;
      case "--author":
        opts.author = args[++i];
        break;
      case "--cover":
        opts.cover = args[++i];
        break;
      case "--digest":
        opts.digest = args[++i];
        break;
      case "--source-url":
        opts.sourceUrl = args[++i];
        break;
      case "--update":
        opts.update = args[++i];
        break;
      case "--dry-run":
        opts.dryRun = true;
        break;
      default:
        if (!args[i].startsWith("-")) opts.file = args[i];
    }
  }

  if (!opts.file) {
    console.error(
      `用法: bun publish.ts <markdown-file> [options]

选项:
  --theme <id>         Alchemy 主题 (默认: wechat-story)
  --title <text>       文章标题 (默认: frontmatter > 首个 # > 文件名)
  --author <name>      作者 (默认: WECHAT_AUTHOR 环境变量)
  --cover <path>       封面图路径 (默认: 首张图片)
  --digest <text>      摘要 (默认: frontmatter.summary)
  --source-url <url>   "阅读原文"链接 (默认: frontmatter.source_url)
  --update <media_id>  覆盖已有草稿 (而非新建)
  --dry-run            只转 HTML，不调微信 API`
    );
    process.exit(1);
  }

  return opts;
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const opts = parseArgs();
  const filePath = resolve(opts.file);
  const baseDir = dirname(filePath);

  if (!existsSync(filePath)) {
    console.error(`文件不存在: ${filePath}`);
    process.exit(1);
  }

  // 1. 解析 Markdown
  const raw = readFileSync(filePath, "utf-8");
  const { data: fm, content: body } = matter(raw);

  const title =
    opts.title ||
    fm.title ||
    body.match(/^#\s+(.+)$/m)?.[1] ||
    basename(filePath, ".md");
  const author = opts.author || DEFAULT_AUTHOR || fm.author || "";
  const digest = opts.digest || fm.summary || "";
  const sourceUrl = opts.sourceUrl || fm.source_url || fm.source?.url || "";
  const theme = opts.theme;

  console.log(`\n  文件: ${basename(filePath)}`);
  console.log(`  标题: ${title}`);
  console.log(`  主题: ${theme}`);
  if (author) console.log(`  作者: ${author}`);
  if (sourceUrl) console.log(`  原文: ${sourceUrl}`);

  // 2. Markdown → HTML
  console.log(`\n→ 调用 Alchemy API 转换 HTML...`);
  const rawHtml = await markdownToHtml(body, theme);
  // Strip HTML comments — they waste chars against the 20000 limit.
  // Typical culprit: <!-- ILLUSTRATION REQUEST ... --> placeholders.
  // Note: 删除注释后可能留下多余空行，导致微信编辑器解析 <ol> 时出现空节点
  const html = rawHtml
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/\n{3,}/g, "\n\n");
  if (html.length < rawHtml.length) {
    console.log(
      `  ✓ HTML 转换完成 (${html.length} chars, 去除注释节省 ${rawHtml.length - html.length} chars)`
    );
  } else {
    console.log(`  ✓ HTML 转换完成 (${html.length} chars)`);
  }

  // 3. 扫描本地图片
  const images = findLocalImages(html, baseDir);
  console.log(`\n→ 发现 ${images.length} 张本地图片`);

  if (opts.dryRun) {
    console.log("\n[DRY RUN] 跳过微信 API 调用");
    images.forEach((img) => console.log(`  - ${img.original}`));

    // 写本地 HTML 并打开预览
    const htmlPath = filePath.replace(/\.md$/, ".preview.html");
    writeFileSync(htmlPath, html, "utf-8");
    console.log(`\n  ✓ HTML 预览已写入: ${htmlPath}`);

    // macOS 自动打开
    Bun.spawnSync({ cmd: ["open", htmlPath] });
    return;
  }

  // 4. 上传图片 + 替换 URL
  let finalHtml = html;
  let thumbMediaId = "";

  if (opts.cover) {
    console.log(`\n→ 上传封面: ${opts.cover}`);
    const { mediaId } = await uploadCoverImage(opts.cover);
    thumbMediaId = mediaId;
  }

  if (images.length > 0) {
    console.log(`\n→ 上传图片到微信 CDN...`);
    const result = await uploadAndReplace(html, images);
    finalHtml = result.html;

    if (!thumbMediaId && result.coverMediaId) {
      thumbMediaId = result.coverMediaId;
      console.log(`  ✓ 首图自动作为封面`);
    }
  }

  if (!thumbMediaId) {
    throw new Error(
      "没有封面图。请用 --cover 指定，或确保文章包含至少一张图片。"
    );
  }

  // 5. 创建或更新草稿
  const articlePayload: WeChatArticle = {
    title,
    content: finalHtml,
    author,
    thumbMediaId,
    digest,
    contentSourceUrl: sourceUrl,
  };

  if (opts.update) {
    console.log(`\n→ 更新微信草稿 ${opts.update}...`);
    await updateDraft(opts.update, articlePayload);
    console.log(`\n  ✓ 草稿更新成功`);
    console.log(`  media_id: ${opts.update}`);
  } else {
    console.log(`\n→ 创建微信草稿...`);
    const mediaId = await createDraft(articlePayload);
    console.log(`\n  ✓ 草稿创建成功`);
    console.log(`  media_id: ${mediaId}`);
  }
  console.log(`  查看: https://mp.weixin.qq.com → 素材管理 → 草稿箱\n`);
}

main().catch((e) => {
  console.error(`\n  ✗ ${e.message}\n`);
  process.exit(1);
});
