# OpenCode

OpenCode was not installed in the validation environment on 2026-07-19. The
adapter follows the upstream OpenClaw launch contract:

```bash
opencode run
```

Before first use, verify `opencode --help` and run a minimal non-mutating smoke.
The runner does not invent an unsafe/bypass flag for this provider and rejects
`--unsafe` when OpenCode is selected.
