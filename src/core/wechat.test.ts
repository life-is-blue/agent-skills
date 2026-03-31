import { describe, expect, it } from "bun:test";

import { cleanHtml, fmtBytes, truncate } from "./wechat";

describe("core/wechat", () => {
  it("truncate should keep short strings", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("truncate should shorten long strings", () => {
    expect(truncate("hello world", 5)).toBe("hello");
  });

  it("fmtBytes should format human readable sizes", () => {
    expect(fmtBytes(512)).toBe("512B");
    expect(fmtBytes(2048)).toBe("2.0KB");
    expect(fmtBytes(2 * 1024 * 1024)).toBe("2.0MB");
  });

  it("cleanHtml should strip comments and collapse extra newlines", () => {
    const input = "<p>a</p><!-- remove -->\n\n\n<p>b</p>";
    expect(cleanHtml(input)).toBe("<p>a</p>\n\n<p>b</p>");
  });
});
