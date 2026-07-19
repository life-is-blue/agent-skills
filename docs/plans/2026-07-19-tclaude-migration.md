# Migrate coding-agent provider to tclaude

## Goal

Replace the deprecated `claude-internal` provider identity with `tclaude` in
both coding-agent adapters, their runner interface, OpenClaw gating, tests, and
current documentation.

## Verified contract

- Local wrapper: `@tencent/tclaude 0.0.9`
- Upstream runtime reported by wrapper: Claude Code `2.1.154`
- Wrapper help: `tclaude --help`
- Forwarded Claude Code help: `tclaude -- --help`
- Non-interactive invocation: `tclaude --print --permission-mode <mode>` with
  prompt on stdin

Only portable command behavior is recorded. Internal login instructions,
company URLs, credentials, and environment details remain out of the repository.

## Changes

1. Replace the runner's accepted provider and auto-detection binary with
   `tclaude`; do not retain a deprecated alias.
2. Rename both provider reference files and update their verified behavior.
3. Replace the OpenClaw installer's `anyBins` gate and launch form.
4. Update tests and user-facing catalog text while leaving the immutable
   OpenClaw upstream snapshot unchanged.

## Acceptance

- The previous provider name remains only in this migration record or immutable
  archive/upstream material, not in active Skill behavior or user documentation.
- Fake-provider tests prove safe and unsafe `tclaude` argument mapping.
- Both Skills pass the standard Skill validator.
- Repository validation and the full pytest suite pass.
