# CodeBuddy coding-agent adapter

## Goal

Add CodeBuddy Code as a portable provider in the `coding-agent` runner using
documented and locally verified headless CLI behavior.

## Evidence

- The `codebuddy-docs` knowledge base documents `codebuddy -p` for headless
  stdin input, permission modes, JSON output, tool restrictions, and session
  resume in `headless.md`, `cli-reference.md`, and `permission-modes.md`.
- Local CodeBuddy Code 2.120.0 exposes `-p/--print`,
  `--permission-mode <acceptEdits|bypassPermissions|default|plan|dontAsk|auto>`,
  `-y/--dangerously-skip-permissions`, tool allow/deny flags, output formats,
  worktrees, and session controls.
- In headless mode, `acceptEdits` still denies Bash calls that would require a
  prompt. `auto` classifies unresolved actions and fails closed; `dontAsk` is
  suitable only when the host supplies a complete allowlist.

## Decisions

- Add provider name `codebuddy`; require the `codebuddy` executable rather than
  silently substituting its optional `cbc` alias.
- Place it after TClaude and before OpenCode in automatic selection order.
- Use `codebuddy -p --permission-mode auto` by default so coding tasks can run
  commands without equating the safe path with permission bypass.
- Map explicit `--unsafe` to
  `codebuddy -p --dangerously-skip-permissions`.
- Keep prompt delivery on stdin and preserve the existing worktree, monitoring,
  log, and verification protocol.
- Add a concise provider reference with only public, portable CLI behavior; do
  not record credentials, authentication steps, or environment-specific URLs.

## Acceptance

- Help, explicit selection, and auto-selection recognize `codebuddy`.
- Fake-provider tests prove safe and unsafe argument mappings without a model
  call.
- The locally installed CLI parses the selected options and completes one
  minimal no-tool smoke without `--unsafe`.
- Skill validation, repository validation, and the full test suite pass.
