export type TextBlock = {
  type: "text";
  text: string;
};

export type ThoughtBlock = {
  type: "thought";
  text: string;
};

export type ToolCallBlock = {
  type: "tool_call";
  name?: string;
  input?: unknown;
};

export type ToolResultBlock = {
  type: "tool_result";
  name?: string;
  content?: unknown;
};

export type ContentBlock =
  | TextBlock
  | ThoughtBlock
  | ToolCallBlock
  | ToolResultBlock;

export type NormalizedMessage = {
  role: string;
  content: ContentBlock[];
  meta?: {
    slop?: number;
  };
};
