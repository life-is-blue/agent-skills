import { z } from "zod";

export const WeChatConfigSchema = z.object({
  apiBase: z.string().url().default("https://api.weixin.qq.com/cgi-bin"),
  appId: z.string().min(1),
  appSecret: z.string().min(1),
  defaultAuthor: z.string().optional(),
});

export type WeChatConfig = z.infer<typeof WeChatConfigSchema>;

export const WeChatArticleSchema = z.object({
  title: z.string().max(32),
  author: z.string().max(16).optional(),
  digest: z.string().max(128).optional(),
  content: z.string().max(20000), // Note: We should also check bytes (1MB)
  content_source_url: z.string().url().optional().or(z.literal("")),
  thumb_media_id: z.string(),
  show_cover_pic: z.number().int().min(0).max(1).default(1),
  need_open_comment: z.number().int().min(0).max(1).default(1),
  only_fans_can_comment: z.number().int().min(0).max(1).default(0),
});

export type WeChatArticle = z.infer<typeof WeChatArticleSchema>;

export const DraftItemSchema = z.object({
  media_id: z.string(),
  content: z.object({
    news_item: z.array(z.any()), // Use any or a recursive structure if needed
  }),
  update_time: z.number(),
});

export type DraftItem = z.infer<typeof DraftItemSchema>;

export const PublishStatusSchema = z.object({
  publish_id: z.string(),
  publish_status: z.number(),
  article_id: z.string().optional(),
  article_detail: z
    .object({
      count: z.number(),
      item: z.array(
        z.object({
          idx: z.number(),
          article_url: z.string(),
        }),
      ),
    })
    .optional(),
  fail_idx: z.array(z.number()).optional(),
});

export type PublishStatus = z.infer<typeof PublishStatusSchema>;
