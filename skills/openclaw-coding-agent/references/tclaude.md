# TClaude compatibility

Verified locally on 2026-07-19 with TClaude 0.0.9 forwarding to Claude Code
2.1.154. Use `tclaude --help` for wrapper commands and `tclaude -- --help` for
the forwarded Claude Code interface.
Do not copy internal authentication instructions, company URLs, tokens, or
environment-specific notices into prompts, logs, or this repository.

## Supported contract

- Non-interactive execution: `tclaude --print`
- Prompt input: positional prompt or stdin in print mode
- Permission modes include `acceptEdits`, `bypassPermissions`, `default`,
  `delegate`, `dontAsk`, and `plan`
- Output formats: `text`, `json`, and `stream-json`
- Input formats: `text` and `stream-json`
- Supports session IDs, resume/continue, MCP config, tool allow/deny lists,
  system prompts, and additional directories

Use `acceptEdits` by default. Use `bypassPermissions` only with explicit user
authorization in a trusted, externally sandboxed checkout.

The wrapper and its underlying Claude Code report separate versions. Treat both
local help surfaces as authoritative and re-run a minimal smoke after an
upgrade.
