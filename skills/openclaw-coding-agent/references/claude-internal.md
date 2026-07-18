# claude-internal compatibility

Verified locally on 2026-07-18 from `claude-internal --help` and `--version`.
Do not copy internal authentication instructions, company URLs, tokens, or
environment-specific notices into prompts, logs, or this repository.

## Supported contract

- Non-interactive execution: `claude-internal --print`
- Prompt input: positional prompt or stdin in print mode
- Permission modes include `acceptEdits`, `bypassPermissions`, `default`,
  `delegate`, `dontAsk`, and `plan`
- Output formats: `text`, `json`, and `stream-json`
- Input formats: `text` and `stream-json`
- Supports session IDs, resume/continue, MCP config, tool allow/deny lists,
  system prompts, and additional directories

Use `acceptEdits` by default. Use `bypassPermissions` only with explicit user
authorization in a trusted, externally sandboxed checkout.

The wrapper and its underlying Claude Code may report separate versions. Treat
the wrapper's local `--help` as authoritative and re-run a minimal smoke after
an upgrade.
