# Codex CLI

Verified locally on 2026-07-18 with Codex CLI 0.144.4.

The runner sends the prompt on stdin to:

```bash
codex exec --sandbox workspace-write --ask-for-approval never -
```

With explicit `--unsafe`, it instead uses:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox -
```

Codex expects a trusted Git repository unless `--skip-git-repo-check` is used.
The adapter intentionally does not skip the check; initialize Git for scratch
work and use an isolated worktree for project changes.

Useful native alternatives include `codex exec review` and `codex exec resume`,
but the portable runner starts a fresh non-interactive execution.
