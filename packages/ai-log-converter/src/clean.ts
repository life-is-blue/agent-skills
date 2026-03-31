import type { ContentBlock } from "./types";

const CLEAN_PATTERNS: Array<[RegExp, string]> = [
  [/<local-command-caveat>[\s\S]*?<\/local-command-caveat>/g, ""],
  [/<thinking>([\s\S]*?)<\/thinking>/g, "[thought] $1"],
  [/<local-command-stdout>([\s\S]*?)<\/local-command-stdout>/g, "$1"],
  [/\n{3,}/g, "\n\n"],
];

export function cleanText(text: string): string {
  if (!text) return "";

  let cleaned = text;
  for (const [pattern, replacement] of CLEAN_PATTERNS) {
    cleaned = cleaned.replace(pattern, replacement);
  }
  return cleaned.trim();
}

export function calculateSlop(blocks: ContentBlock[]): number {
  const thoughtLength = blocks
    .filter((block) => block.type === "thought")
    .reduce((sum, block) => sum + (block.text?.length ?? 0), 0);

  const textLength = blocks
    .filter((block) => block.type === "text")
    .reduce((sum, block) => sum + (block.text?.length ?? 0), 0);

  if (textLength === 0) {
    return thoughtLength > 0 ? 1 : 0;
  }

  return Number((thoughtLength / (thoughtLength + textLength)).toFixed(3));
}
