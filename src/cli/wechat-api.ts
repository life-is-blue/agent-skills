/**
 * wechat-api.ts — 微信公众号 API 共享层
 *
 * 封装 token 管理、错误处理、所有 API 调用。
 * publish.ts 和 wechat-manage.ts 共用。
 */

// ─── Config ──────────────────────────────────────────────────────────────────

export const WECHAT_API =
  process.env["WECHAT_API_BASE"] || "https://api.weixin.qq.com/cgi-bin";
const APPID = process.env["WECHAT_APPID"] || "";
const APPSECRET = process.env["WECHAT_APPSECRET"] || "";

export const DEFAULT_AUTHOR = process.env["WECHAT_AUTHOR"] || "";

export const LIMITS = {
  TITLE_CHARS: 32,
  AUTHOR_CHARS: 16,
  DIGEST_CHARS: 128,
  CONTENT_CHARS: 20_000,
  CONTENT_BYTES: 1_000_000, // 1MB
  UPLOADIMG_BYTES: 1_000_000, // 1MB，仅 jpg/png
  MATERIAL_BYTES: 10_000_000, // 10MB
} as const;

export const WECHAT_ERRORS: Record<number, string> = {
  [-1]: "系统繁忙，请稍后重试",
  40001: "AppSecret 错误或不属于此 AppID",
  40002: "grant_type 字段值应为 client_credential",
  40005: "不支持的文件类型",
  40009: "图片大小超出限制",
  40013: "AppID 不合法",
  40125: "AppSecret 无效",
  40164: "调用接口的 IP 不在白名单中",
  41001: "缺少 access_token 参数",
  42001: "access_token 过期",
  45009: "API 调用次数已达今日上限",
  47003: "参数错误，请检查必填字段",
  48001: "API 功能未授权，请确认公众号类型",
};

// ─── Token ───────────────────────────────────────────────────────────────────

let cachedToken = { token: "", expiresAt: 0 };

/**
 * 获取 access_token（stable_token 版本）
 *
 * 和基础版 /cgi-bin/token 互相隔离，不会和公众号后台互踩。
 * 在有效期内重复调用返回相同 token（平台自动续期）。
 */
export async function getAccessToken(): Promise<string> {
  if (cachedToken.token && Date.now() < cachedToken.expiresAt - 300_000) {
    return cachedToken.token;
  }

  if (!APPID || !APPSECRET) {
    throw new Error(
      "缺少微信凭证。请在 .env 中设置 WECHAT_APPID 和 WECHAT_APPSECRET",
    );
  }

  const res = await fetch(`${WECHAT_API}/stable_token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "client_credential",
      appid: APPID,
      secret: APPSECRET,
    }),
  });
  const data = (await res.json()) as any;

  handleWeChatError(data, "获取 access_token");

  cachedToken = {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  return data.access_token;
}

/** 清除 token 缓存，下次调用 getAccessToken 会重新获取 */
export function clearTokenCache(): void {
  cachedToken = { token: "", expiresAt: 0 };
}

// ─── Error Handling ──────────────────────────────────────────────────────────

export function handleWeChatError(data: any, context: string): void {
  if (!data.errcode || data.errcode === 0) return;

  const code = data.errcode;
  const msg = WECHAT_ERRORS[code] || data.errmsg || "未知错误";
  let detail = `${context}失败 (${code}): ${msg}`;

  if (code === 40164) {
    detail +=
      "\n\n  解决: 登录 mp.weixin.qq.com → 设置与开发 → 基本配置 → IP白名单";
    detail += "\n  查看本机公网 IP: curl https://ifconfig.me";
  } else if (code === 40001 || code === 40125 || code === 40013) {
    detail +=
      "\n\n  解决: 检查 .env 中 WECHAT_APPID / WECHAT_APPSECRET 是否正确";
  } else if (code === 45009) {
    detail += "\n\n  解决: 今日 API 配额已用完，明天再试";
  }

  throw new Error(detail);
}

/**
 * 带 token 过期自动重试的 API 调用包装
 *
 * 遇到 42001/40001 时自动刷新 token 重试一次。
 */
export async function withRetry<T>(
  fn: (token: string) => Promise<T>,
): Promise<T> {
  const token = await getAccessToken();
  try {
    return await fn(token);
  } catch (e: any) {
    // 检查是否是 token 过期错误
    if (e.message?.includes("(42001)") || e.message?.includes("(40001)")) {
      console.log("  access_token 过期，刷新中...");
      clearTokenCache();
      const newToken = await getAccessToken();
      return await fn(newToken);
    }
    throw e;
  }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

export function truncate(s: string, maxChars: number): string {
  if (s.length <= maxChars) return s;
  console.log(
    `  [WARN] 截断: "${s.slice(0, 20)}..." ${s.length} → ${maxChars} 字符`,
  );
  return s.slice(0, maxChars);
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}

// ─── Types ───────────────────────────────────────────────────────────────────

/** 草稿列表中的单篇文章 */
export interface DraftArticle {
  title: string;
  author: string;
  digest: string;
  content: string;
  content_source_url: string;
  thumb_media_id: string;
  show_cover_pic: number;
  url: string;
  thumb_url: string;
}

/** 草稿列表项 */
export interface DraftItem {
  media_id: string;
  content: { news_item: DraftArticle[] };
  update_time: number;
}

/** 草稿列表批量查询结果 */
export interface DraftBatchResult {
  total_count: number;
  item_count: number;
  item: DraftItem[];
}

/** 发布状态 */
export interface PublishStatus {
  publish_id: string;
  publish_status: 0 | 1 | 2 | 3; // 0:成功 1:发布中 2+:id 不对 3:审核不通过
  article_id?: string;
  article_detail?: {
    count: number;
    item: { idx: number; article_url: string }[];
  };
  fail_idx?: number[];
}

// ─── Draft APIs ──────────────────────────────────────────────────────────────

/** 创建草稿，返回 media_id */
export async function apiDraftAdd(body: {
  articles: Record<string, any>[];
}): Promise<string> {
  return withRetry(async (token) => {
    const res = await fetch(`${WECHAT_API}/draft/add?access_token=${token}`, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(body),
    });
    const data = (await res.json()) as any;
    handleWeChatError(data, "创建草稿");
    return data.media_id;
  });
}

/** 获取草稿总数 */
export async function apiDraftCount(): Promise<number> {
  return withRetry(async (token) => {
    const res = await fetch(`${WECHAT_API}/draft/count?access_token=${token}`);
    const data = (await res.json()) as any;
    handleWeChatError(data, "查询草稿数量");
    return data.total_count;
  });
}

/** 批量获取草稿列表 */
export async function apiDraftBatchGet(
  offset = 0,
  count = 20,
  noContent = true,
): Promise<DraftBatchResult> {
  return withRetry(async (token) => {
    const res = await fetch(
      `${WECHAT_API}/draft/batchget?access_token=${token}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offset, count, no_content: noContent ? 1 : 0 }),
      },
    );
    const data = (await res.json()) as any;
    handleWeChatError(data, "查询草稿列表");
    return data;
  });
}

/** 删除草稿 */
export async function apiDraftDelete(mediaId: string): Promise<void> {
  return withRetry(async (token) => {
    const res = await fetch(
      `${WECHAT_API}/draft/delete?access_token=${token}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ media_id: mediaId }),
      },
    );
    const data = (await res.json()) as any;
    handleWeChatError(data, `删除草稿 ${mediaId}`);
  });
}

/** 更新草稿中的指定文章 */
export async function apiDraftUpdate(
  mediaId: string,
  index: number,
  articles: Record<string, any>,
): Promise<void> {
  return withRetry(async (token) => {
    const res = await fetch(
      `${WECHAT_API}/draft/update?access_token=${token}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          media_id: mediaId,
          index,
          articles,
        }),
      },
    );
    const data = (await res.json()) as any;
    handleWeChatError(data, `更新草稿 ${mediaId} index=${index}`);
  });
}

// ─── Freepublish APIs ────────────────────────────────────────────────────────

/** 提交发布（从草稿发布到公众号） */
export async function apiFreepublishSubmit(mediaId: string): Promise<string> {
  return withRetry(async (token) => {
    const res = await fetch(
      `${WECHAT_API}/freepublish/submit?access_token=${token}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ media_id: mediaId }),
      },
    );
    const data = (await res.json()) as any;
    handleWeChatError(data, `提交发布 ${mediaId}`);
    return data.publish_id;
  });
}

/** 查询发布状态 */
export async function apiFreepublishGet(
  publishId: string,
): Promise<PublishStatus> {
  return withRetry(async (token) => {
    const res = await fetch(
      `${WECHAT_API}/freepublish/get?access_token=${token}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ publish_id: publishId }),
      },
    );
    const data = (await res.json()) as any;
    handleWeChatError(data, `查询发布状态 ${publishId}`);
    return data;
  });
}
