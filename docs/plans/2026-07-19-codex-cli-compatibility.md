# Codex CLI compatibility

## Goal

Restore the coding-agent adapters after a live forward test showed that Codex
CLI 0.144.6 rejects the previous non-interactive approval flag placement.

## Evidence

- `codex exec --sandbox workspace-write --ask-for-approval never --help`
  exits 2 with `unexpected argument '--ask-for-approval'`.
- `codex --ask-for-approval never exec --sandbox workspace-write --help`
  exits 0; current local help defines approval policy as a global option.
- A coding-agent session using the old command terminated before producing
  output, so the Skill evolution forward test could not start.

## Changes

- Move the safe Codex approval option before the `exec` subcommand in the
  portable runner and OpenClaw-specific invocation.
- Update the portable Codex reference and fake-provider assertion.
- Preserve the explicit unsafe mapping unchanged.

## Acceptance

- The corrected safe command parses under the installed Codex CLI.
- Fake-provider lifecycle tests assert the corrected argument order.
- A live, sandboxed coding-agent smoke reaches a terminal status and produces
  a non-empty log without permission bypass.
- Repository validation and tests pass.
