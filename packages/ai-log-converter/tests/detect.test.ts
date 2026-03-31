import { describe, expect, it } from "bun:test";

import { detectFormat, isMetadataEntry } from "../src/detect";

describe("detect", () => {
  it("detects gemini after metadata lines", () => {
    const samples = [
      { type: "info", msg: "meta" },
      { type: "model", parts: [{ text: "hello" }] },
    ];

    expect(detectFormat(samples)).toBe("gemini");
  });

  it("skips codex reasoning metadata", () => {
    const samples = [
      { type: "response_item", payload: { type: "reasoning" } },
      { type: "response_item", payload: { type: "message", role: "assistant" } },
    ];

    expect(detectFormat(samples)).toBe("codex");
  });

  it("identifies metadata entries", () => {
    expect(isMetadataEntry({ type: "info" })).toBe(true);
    expect(isMetadataEntry({ type: "message" })).toBe(false);
  });
});
