#!/usr/bin/env bun
/**
 * wechat-manage.ts — 微信公众号草稿管理
 *
 * 子命令:
 *   draft list              列出所有草稿
 *   draft delete <media_id> 删除草稿
 *   draft update <media_id> <markdown_file> 覆盖草稿内容
 *   submit <media_id>       提交发布（草稿→正式发布）
 *   status <publish_id>     查询发布状态
 *
 * 用法:
 *   bun wechat-manage.ts draft list
 *   bun wechat-manage.ts draft delete MEDIA_ID
 *   bun wechat-manage.ts draft update MEDIA_ID path/to/article.md
 *   bun wechat-manage.ts submit MEDIA_ID
 *   bun wechat-manage.ts status PUBLISH_ID
 */

import {
  apiDraftBatchGet,
  apiDraftCount,
  apiDraftDelete,
  apiDraftUpdate,
  apiFreepublishSubmit,
  apiFreepublishGet,
  type DraftItem,
  type PublishStatus,
} from "./wechat-api";

// ─── Formatters ──────────────────────────────────────────────────────────────

function fmtDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDraft(item: DraftItem, idx: number): string {
  const articles = item.content.news_item;
  const title = articles[0]?.title || "(无标题)";
  const count = articles.length;
  const time = fmtDate(item.update_time);
  const multi = count > 1 ? ` (+${count - 1} 篇)` : "";
  return `  ${idx + 1}. ${title}${multi}\n     media_id: ${item.media_id}\n     更新: ${time}`;
}

function fmtPublishStatus(status: PublishStatus): string {
  const statusMap: Record<number, string> = {
    0: "发布成功",
    1: "发布中",
    2: "原创审核中",
    3: "审核不通过",
    4: "人工审核中",
  };
  const label = statusMap[status.publish_status] ?? `未知(${status.publish_status})`;
  let out = `  状态: ${label}`;

  if (status.article_id) {
    out += `\n  article_id: ${status.article_id}`;
  }
  if (status.article_detail?.item?.length) {
    out += "\n  文章链接:";
    for (const a of status.article_detail.item) {
      out += `\n    ${a.idx + 1}. ${a.article_url}`;
    }
  }
  if (status.fail_idx?.length) {
    out += `\n  失败文章序号: ${status.fail_idx.join(", ")}`;
  }
  return out;
}

// ─── Commands ────────────────────────────────────────────────────────────────

async function cmdDraftList(): Promise<void> {
  const total = await apiDraftCount();
  console.log(`\n  草稿总数: ${total}`);

  if (total === 0) {
    console.log("  (空)\n");
    return;
  }

  // 分页拉取所有草稿
  const allDrafts: DraftItem[] = [];
  let offset = 0;
  const pageSize = 20;
  while (offset < total) {
    const batch = await apiDraftBatchGet(offset, pageSize);
    allDrafts.push(...batch.item);
    offset += pageSize;
  }

  console.log("");
  allDrafts.forEach((item, i) => console.log(fmtDraft(item, i)));
  console.log("");
}

async function cmdDraftDelete(mediaId: string): Promise<void> {
  await apiDraftDelete(mediaId);
  console.log(`\n  ✓ 草稿已删除: ${mediaId}\n`);
}

async function cmdSubmit(mediaId: string): Promise<void> {
  const publishId = await apiFreepublishSubmit(mediaId);
  console.log(`\n  ✓ 已提交发布`);
  console.log(`  publish_id: ${publishId}`);
  console.log(`\n  查询状态: bun wechat-manage.ts status ${publishId}\n`);
}

async function cmdStatus(publishId: string): Promise<void> {
  const status = await apiFreepublishGet(publishId);
  console.log(`\n${fmtPublishStatus(status)}\n`);
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

function printUsage(): void {
  console.error(`用法: bun wechat-manage.ts <command> [args]

命令:
  draft list                列出所有草稿
  draft delete <media_id>   删除指定草稿
  draft update <media_id> <file>  覆盖草稿 (等同 publish.ts --update)
  submit <media_id>         提交发布（草稿 → 正式文章）
  status <publish_id>       查询发布状态`);
  process.exit(1);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length === 0) printUsage();

  const cmd = args[0];

  switch (cmd) {
    case "draft": {
      const sub = args[1];
      if (sub === "list") {
        await cmdDraftList();
      } else if (sub === "delete") {
        const mediaId = args[2];
        if (!mediaId) {
          console.error("缺少 media_id。用法: bun wechat-manage.ts draft delete <media_id>");
          process.exit(1);
        }
        await cmdDraftDelete(mediaId);
      } else if (sub === "update") {
        const mediaId = args[2];
        const file = args[3];
        if (!mediaId || !file) {
          console.error("用法: bun publish.ts <file> --update <media_id>\n  draft update 请直接使用 publish.ts --update");
          process.exit(1);
        }
        // 委托给 publish.ts
        const { execSync } = await import("child_process");
        execSync(`bun ${import.meta.dir}/publish.ts "${file}" --update "${mediaId}"`, { stdio: "inherit" });
      } else {
        console.error(`未知子命令: draft ${sub || ""}`);
        printUsage();
      }
      break;
    }
    case "submit": {
      const mediaId = args[1];
      if (!mediaId) {
        console.error("缺少 media_id。用法: bun wechat-manage.ts submit <media_id>");
        process.exit(1);
      }
      await cmdSubmit(mediaId);
      break;
    }
    case "status": {
      const publishId = args[1];
      if (!publishId) {
        console.error("缺少 publish_id。用法: bun wechat-manage.ts status <publish_id>");
        process.exit(1);
      }
      await cmdStatus(publishId);
      break;
    }
    default:
      console.error(`未知命令: ${cmd}`);
      printUsage();
  }
}

main().catch((e) => {
  console.error(`\n  ✗ ${e.message}\n`);
  process.exit(1);
});
