export type DetectedFormat = "claude" | "gemini" | "codebuddy" | "codex";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null) return null;
  return value as Record<string, unknown>;
}

export function isMetadataEntry(sample: Record<string, unknown>): boolean {
  if (sample["isMeta"] || sample["isSummary"]) {
    return true;
  }

  const type = sample["type"];
  if (
    type === "info" ||
    type === "session_meta" ||
    type === "event_msg" ||
    type === "file-history-snapshot" ||
    type === "topic"
  ) {
    return true;
  }

  if (type === "response_item") {
    const payload = asRecord(sample["payload"]);
    const payloadType = payload?.["type"];
    if (payloadType === "reasoning") {
      return true;
    }

    if (payloadType === "message") {
      const role = payload?.["role"];
      if (role === "system" || role === "developer") {
        return true;
      }
    }
  }

  return false;
}

export function detectFormat(
  samples: Iterable<Record<string, unknown>>,
): DetectedFormat | null {
  for (const sample of samples) {
    if (isMetadataEntry(sample)) continue;

    const type = sample["type"];
    if (
      typeof type === "string" &&
      (sample["messageId"] !== undefined ||
        sample["message"] !== undefined ||
        sample["snapshot"] !== undefined)
    ) {
      return "claude";
    }

    if (
      sample["messages"] !== undefined ||
      type === "user" ||
      type === "model" ||
      type === "gemini"
    ) {
      return "gemini";
    }

    if (type !== undefined && sample["payload"] !== undefined) {
      return "codex";
    }

    if (
      type !== undefined &&
      sample["role"] !== undefined &&
      sample["content"] !== undefined
    ) {
      return "codebuddy";
    }
  }

  return null;
}
