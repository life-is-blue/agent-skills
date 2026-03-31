import type { PublishStatus, WeChatConfig } from "../schema/wechat";

export class WeChatService {
  private config: WeChatConfig;
  private cachedToken: { token: string; expiresAt: number } = {
    token: "",
    expiresAt: 0,
  };

  constructor(config: WeChatConfig) {
    this.config = config;
  }

  async getAccessToken(): Promise<string> {
    if (
      this.cachedToken.token &&
      Date.now() < this.cachedToken.expiresAt - 300_000
    ) {
      return this.cachedToken.token;
    }

    const res = await fetch(`${this.config.apiBase}/stable_token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grant_type: "client_credential",
        appid: this.config.appId,
        secret: this.config.appSecret,
      }),
    });
    const data = (await res.json()) as any;
    this.handleWeChatError(data, "获取 access_token");

    this.cachedToken = {
      token: data.access_token,
      expiresAt: Date.now() + data.expires_in * 1000,
    };
    return data.access_token;
  }

  private handleWeChatError(data: any, context: string): void {
    if (!data.errcode || data.errcode === 0) return;
    throw new Error(
      `${context}失败 (${data.errcode}): ${data.errmsg || "未知错误"}`,
    );
  }

  async withRetry<T>(fn: (token: string) => Promise<T>): Promise<T> {
    const token = await this.getAccessToken();
    try {
      return await fn(token);
    } catch (e: any) {
      if (e.message?.includes("(42001)") || e.message?.includes("(40001)")) {
        this.cachedToken = { token: "", expiresAt: 0 };
        const newToken = await this.getAccessToken();
        return await fn(newToken);
      }
      throw e;
    }
  }

  async addDraft(articles: any[]): Promise<string> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/draft/add?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json; charset=utf-8" },
          body: JSON.stringify({ articles }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, "创建草稿");
      return data.media_id;
    });
  }

  async getDraftCount(): Promise<number> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/draft/count?access_token=${token}`,
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, "查询草稿数量");
      return data.total_count;
    });
  }

  async getDraftBatch(offset = 0, count = 20): Promise<any> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/draft/batchget?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ offset, count, no_content: 1 }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, "查询草稿列表");
      return data;
    });
  }

  async deleteDraft(mediaId: string): Promise<void> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/draft/delete?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ media_id: mediaId }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `删除草稿 ${mediaId}`);
    });
  }

  async updateDraft(
    mediaId: string,
    index: number,
    articles: any,
  ): Promise<void> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/draft/update?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json; charset=utf-8" },
          body: JSON.stringify({ media_id: mediaId, index, articles }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `更新草稿 ${mediaId}`);
    });
  }

  async submitPublish(mediaId: string): Promise<string> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/freepublish/submit?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ media_id: mediaId }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `提交发布 ${mediaId}`);
      return data.publish_id;
    });
  }

  async getPublishStatus(publishId: string): Promise<PublishStatus> {
    return this.withRetry(async (token) => {
      const res = await fetch(
        `${this.config.apiBase}/freepublish/get?access_token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ publish_id: publishId }),
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `查询发布状态 ${publishId}`);
      return data;
    });
  }

  async uploadArticleImage(blob: Blob, filename: string): Promise<string> {
    return this.withRetry(async (token) => {
      const form = new FormData();
      form.append("media", blob, filename);
      const res = await fetch(
        `${this.config.apiBase}/media/uploadimg?access_token=${token}`,
        {
          method: "POST",
          body: form,
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `上传文章图片 ${filename}`);
      return data.url;
    });
  }

  async uploadMaterialImage(
    blob: Blob,
    filename: string,
  ): Promise<{ mediaId: string; url: string }> {
    return this.withRetry(async (token) => {
      const form = new FormData();
      form.append("media", blob, filename);
      const res = await fetch(
        `${this.config.apiBase}/material/add_material?access_token=${token}&type=image`,
        {
          method: "POST",
          body: form,
        },
      );
      const data = (await res.json()) as any;
      this.handleWeChatError(data, `上传封面素材 ${filename}`);
      return { mediaId: data.media_id, url: data.url || "" };
    });
  }
}
