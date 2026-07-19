# Codex CLI

Verified locally on 2026-07-19 with Codex CLI 0.144.6.

The runner sends the prompt on stdin to:

```bash
codex --ask-for-approval never exec --sandbox workspace-write -
```

With explicit `--unsafe`, it instead uses:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox -
```

Codex expects a trusted Git repository unless `--skip-git-repo-check` is used.
The adapter intentionally does not skip the check; initialize Git for scratch
work and use an isolated worktree for project changes.

`--ask-for-approval` is a global option in this version and must precede the
`exec` subcommand. Confirm both `codex --help` and `codex exec --help` after a
CLI upgrade because argument placement is version-sensitive.

Useful native alternatives include `codex exec review` and `codex exec resume`,
but the portable runner starts a fresh non-interactive execution.
