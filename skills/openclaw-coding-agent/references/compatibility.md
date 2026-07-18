# Provider compatibility

| Provider | OpenClaw PTY | Non-interactive command | Default permission posture |
|---|---:|---|---|
| Codex | yes | `codex exec ... -` | workspace-write sandbox, never ask |
| Claude Code | no | `claude --print` | `acceptEdits` |
| claude-internal | no | `claude-internal --print` | `acceptEdits` |
| OpenCode | yes | `opencode run` | provider default |

Before changing a command, verify local `<binary> --help` and run one minimal
non-mutating smoke. Documentation from another distribution is not sufficient
evidence for a modified CLI.

The adapted Skill deliberately differs from upstream by avoiding permission
bypass as the default and by supporting `claude-internal`.
