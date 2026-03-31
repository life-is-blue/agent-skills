import { describe, expect, it } from "bun:test";

import { calculateSlop, cleanText } from "../src/clean";
import type { ContentBlock } from "../src/types";

describe("clean", () => {
  it("removes caveat tags and collapses blank lines", () => {
    const input = "a<local-command-caveat>x</local-command-caveat>\n\n\n b";
    expect(cleanText(input)).toBe("a\n\n b");
  });

  it("calculates slop ratio", () => {
    const blocks: ContentBlock[] = [
      { type: "thought", text: "xx" },
      { type: "text", text: "xx" },
    ];
    expect(calculateSlop(blocks)).toBe(0.5);
  });
});
