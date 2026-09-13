# Claude Code

Verified locally on 2026-07-18 with Claude Code 2.1.126.

The runner sends the prompt on stdin to:

```bash
claude --print --permission-mode acceptEdits
```

With explicit `--unsafe`, it uses:

```bash
claude --print --permission-mode bypassPermissions
```

Print mode is non-interactive and does not require a PTY. Claude Code supports
`text`, `json`, and `stream-json` output, but the runner preserves raw combined
output in its log rather than parsing provider events.

Re-run `claude --help` after upgrades; public CLI flags are the source of truth
for this provider.

Local help rechecked on 2026-09-14 exposes `--worktree [name]` and native
background sessions. The portable runner intentionally uses neither: coordinator
owns the registered worktree and the runner owns its monitored process. Changing
cwd alone must not be claimed to activate Claude's native worktree-isolation
checks. Keep the chosen sandbox and independent review checkout. No automatic
`.worktreeinclude` processing or credential copying is added by this adapter.

See [official worktree lifecycle](https://code.claude.com/docs/en/worktrees).
