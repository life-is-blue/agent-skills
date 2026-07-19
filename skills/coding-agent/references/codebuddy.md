# CodeBuddy Code

Verified locally on 2026-07-19 with CodeBuddy Code 2.120.0. The public
`codebuddy-docs` knowledge base was checked first, then every runner flag was
confirmed with local `codebuddy --help`.

The runner sends the prompt on stdin to:

```bash
codebuddy -p --permission-mode auto
```

Headless `auto` sends unresolved permission requests to CodeBuddy's classifier
and fails closed when classification is unavailable. It can still reject or
stop a run; inspect the log instead of treating that as provider success.

With explicit `--unsafe`, the runner uses:

```bash
codebuddy -p --dangerously-skip-permissions
```

This bypass path is appropriate only inside the trusted, externally isolated
worktree required by the parent Skill. Do not infer `--unsafe` from headless
execution alone.

CodeBuddy also supports `--output-format text|json|stream-json`, `--resume`,
`--continue`, `--max-turns`, `--tools`, `--allowedTools`, `--disallowedTools`,
MCP configuration, built-in worktrees, and its `cbc` alias. The portable runner
uses text output, its own worktree lifecycle, and the canonical `codebuddy`
binary. Do not silently fall back to `cbc` if that binary is missing.

Trust current local help plus a minimal smoke after upgrades. Do not copy
credentials, authentication procedures, private endpoints, or user settings
into prompts or this reference.
