# TClaude

Verified locally on 2026-07-19 with TClaude 0.0.9 forwarding to Claude Code
2.1.154. This reference records only portable CLI
behavior and intentionally excludes internal URLs, credentials, authentication
procedures, and environment-specific notices.

The runner sends the prompt on stdin to:

```bash
tclaude --print --permission-mode acceptEdits
```

With explicit `--unsafe`, it uses `bypassPermissions` instead.

The wrapper forwards non-wrapper arguments to Claude Code. Use `tclaude --help`
for wrapper commands and `tclaude -- --help` for the forwarded Claude Code
interface. It supports text/JSON/stream-JSON output, session resume, tool
allow/deny lists, MCP configuration, and additional directories. Always trust
both local help surfaces plus a minimal smoke over public Claude documentation.
