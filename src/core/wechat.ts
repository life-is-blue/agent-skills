/**
 * core/wechat.ts — WeChat tool core logic (Pure functions)
 */

export function truncate(s: string, maxChars: number): string {
  if (s.length <= maxChars) return s;
  return s.slice(0, maxChars);
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}

export function cleanHtml(rawHtml: string): string {
  // Strip HTML comments — they waste chars against the 20000 limit.
  // Typical culprit: <!-- ILLUSTRATION REQUEST ... --> placeholders.
  return rawHtml.replace(/<!--[\s\S]*?-->/g, "").replace(/\n{3,}/g, "\n\n");
}

export function fmtDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
