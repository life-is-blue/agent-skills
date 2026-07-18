---
name: openclaw-coding-agent
description: Delegate substantial coding work from OpenClaw to Codex, Claude Code, claude-internal, or OpenCode as monitored background workers. Use for feature builds, large refactors, PR reviews, and issue-to-PR loops that need OpenClaw process sessions and completion notifications; do not use for simple edits or read-only lookup.
---

# OpenClaw Coding Agent

Run coding CLIs as OpenClaw-owned background workers. Keep provider selection,
Git preparation, monitoring, and notification delivery in the parent agent.

This is an adapted Skill. See [provenance](references/provenance.md). The
immutable [upstream snapshot](references/upstream-SKILL.md) and
[license](references/LICENSE.openclaw) are preserved beside it.

## Install as the OpenClaw override

The repository name avoids colliding with the portable `coding-agent` Skill.
Install it into OpenClaw under the upstream name `coding-agent`:

```bash
bash scripts/install-openclaw --workspace /path/to/openclaw-workspace
# or: bash scripts/install-openclaw --global
```

The installer stages an atomic replacement and refuses to overwrite an existing
override unless `--force` is explicit. Do not install the portable
`coding-agent` and this OpenClaw override into the same OpenClaw skill root.

## Route

1. Honor an explicitly requested provider.
2. Otherwise choose the first suitable installed provider: `codex`, `claude`,
   `claude-internal`, then `opencode`.
3. Verify the selected binary with `command -v` and local `--help` before using
   a launch form that has not been smoke-tested on this host.
4. Do the work directly when it is a simple edit, a quick explanation, or a
   read-only lookup.

Read [claude-internal compatibility](references/claude-internal.md) before
selecting `claude-internal`.

## Hard rules

- Always launch the worker with `background:true`.
- Use `pty:true` for Codex and OpenCode. Do not request a PTY for Claude print
  mode or claude-internal print mode.
- Capture a real OpenClaw notification route before launch. If none exists,
  state that automatic completion notification is unavailable.
- Monitor through OpenClaw `process`; do not kill a slow worker without cause.
- Never run a coding worker inside `~/.openclaw`, `$OPENCLAW_STATE_DIR`, an
  active OpenClaw state directory, or OpenClaw's primary checkout.
- Never pass permission-bypass flags for an untrusted checkout. Use the
  repository's approved sandbox/review workflow for contributor-controlled
  refs.
- If a worker fails or hangs, diagnose, respawn, or ask the user. Do not
  silently switch to hand-editing.

## Prepare modifying work

For changes to a Git repository:

1. Identify and fetch the canonical remote and target base.
2. Classify the source ref as trusted or untrusted before materializing it.
3. For trusted work, create an isolated worktree from the fetched base/source.
4. Verify and record the start SHA, worktree path, branch, canonical remote,
   and target base SHA.
5. Put those values in the worker prompt. Require the worker to verify its
   current directory and initial `HEAD` before editing.
6. Do not rebase, reset, force-push, or otherwise rewrite an existing/shared
   branch unless explicitly authorized.

Scratch work must still use a temporary initialized Git repository when Codex
requires repository trust.

## Build the prompt

Write the complete prompt to a temporary file to avoid shell quoting bugs. It
must include the task, constraints, expected proof, Git preparation receipt,
and notification block.

```text
Git preparation:
- canonical remote: <remote>
- target base branch: <branch>
- fetched target base SHA: <sha>
- prepared source ref/start SHA: <ref> / <sha>
- isolated worktree: <path>
- working branch: <branch>

Notification route:
- channel: <channel>
- target: <target>
- account/reply_to/thread_id: <only when present>

When finished, send exactly one completion or failure message with
`openclaw message send`. Do not rely on heartbeat or system events.
```

## Launch forms

Use safe provider permissions by default. Permission bypass is allowed only
when the user has authorized it and the checkout is trusted and externally
sandboxed.

Codex:

```text
bash pty:true background:true workdir:/path/worktree command:"codex exec --sandbox workspace-write --ask-for-approval never - < \"$PROMPT\""
```

Claude Code:

```text
bash background:true workdir:/path/worktree command:"claude --permission-mode acceptEdits --print < \"$PROMPT\""
```

claude-internal:

```text
bash background:true workdir:/path/worktree command:"claude-internal --permission-mode acceptEdits --print < \"$PROMPT\""
```

OpenCode:

```text
bash pty:true background:true workdir:/path/worktree command:"opencode run < \"$PROMPT\""
```

## Monitor and finish

- Return the worktree and OpenClaw `sessionId` immediately after launch.
- Use `process list`, `poll`, and `log` to monitor; use `submit`, `write`, or
  `paste` only when the worker requests input.
- Update the user on milestones, worker questions, errors, required user
  action, and completion—not on every poll.
- On completion, inspect the diff and run the repository's relevant validation.
- For new branches, refresh the target base and verify ancestry before the
  final push. Do not force-push.
- If terminated, say who/what stopped it and why.

Read [provider compatibility](references/compatibility.md) when updating
provider commands. Read the upstream snapshot only when comparing or syncing
behavior.
