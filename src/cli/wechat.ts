#!/usr/bin/env bun
import { fmtDate } from "../core/wechat";
import { WeChatConfigSchema } from "../schema/wechat";
import { WeChatService } from "../services/wechat";

async function main() {
  const config = WeChatConfigSchema.parse({
    appId: process.env["WECHAT_APPID"],
    appSecret: process.env["WECHAT_APPSECRET"],
    defaultAuthor: process.env["WECHAT_AUTHOR"],
  });

  const service = new WeChatService(config);
  const args = process.argv.slice(2);
  const cmd = args[0];

  if (cmd === "draft") {
    const sub = args[1];
    if (sub === "list") {
      const total = await service.getDraftCount();
      console.log(`\n  草稿总数: ${total}`);
      const batch = await service.getDraftBatch(0, 20);
      batch.item.forEach((item: any, i: number) => {
        console.log(
          `  ${i + 1}. ${item.content.news_item[0].title}\n     media_id: ${
            item.media_id
          }\n     更新: ${fmtDate(item.update_time)}`,
        );
      });
    } else if (sub === "delete") {
      await service.deleteDraft(args[2]);
      console.log("✓ 已删除");
    } else if (sub === "update") {
      const mediaId = args[2];
      const file = args[3];
      if (!mediaId || !file) {
        console.error("用法: bun run wechat draft update <media_id> <file.md>");
        process.exit(1);
      }
      const { execSync } = await import("child_process");
      execSync(
        `bun ${import.meta.dir}/publish.ts "${file}" --update "${mediaId}"`,
        {
          stdio: "inherit",
        },
      );
    } else {
      console.error(`未知子命令: draft ${sub || ""}`);
      process.exit(1);
    }
  } else if (cmd === "submit") {
    const pid = await service.submitPublish(args[1]);
    console.log(`✓ 已提交, publish_id: ${pid}`);
  } else if (cmd === "status") {
    const status = await service.getPublishStatus(args[1]);
    console.log(JSON.stringify(status, null, 2));
  } else {
    console.log(
      "用法: bun run wechat <draft list|draft delete|draft update|submit|status>",
    );
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
