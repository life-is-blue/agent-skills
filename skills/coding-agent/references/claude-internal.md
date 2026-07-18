# claude-internal

Verified locally on 2026-07-18. This reference records only portable CLI
behavior and intentionally excludes internal URLs, credentials, authentication
procedures, and environment-specific notices.

The runner sends the prompt on stdin to:

```bash
claude-internal --print --permission-mode acceptEdits
```

With explicit `--unsafe`, it uses `bypassPermissions` instead.

The local wrapper supports text/JSON/stream-JSON output, session resume,
tool allow/deny lists, MCP configuration, and additional directories. It may
report both wrapper and underlying Claude Code versions. Always trust the local
`claude-internal --help` plus a minimal smoke over public Claude documentation.
