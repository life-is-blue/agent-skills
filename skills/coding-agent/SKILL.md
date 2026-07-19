---
name: coding-agent
description: Delegate substantial coding work to Codex, Claude Code, TClaude, or OpenCode through a portable monitored background runner. Use for feature implementation, large refactors, code reviews, and long issue-to-PR work; do not use for simple edits, read-only lookup, or tasks that must remain in the current agent thread.
---

# Coding Agent

Use the bundled `scripts/coding-agent-run` adapter to launch and monitor coding
CLIs without depending on OpenClaw.

## Route

- Honor an explicitly requested provider.
- With `--agent auto`, select the first installed provider in this order:
  Codex, Claude Code, TClaude, OpenCode.
- Handle simple edits and read-only questions directly.
- Do not silently switch providers after a failure. Report the failure and
  retry or ask.

Read the matching provider reference before first use on a host or after a CLI
upgrade.

## Prepare the workspace

For a modifying task in Git:

1. Confirm the target repository, canonical remote, target base, and trust of
   the source ref.
2. Use the repository's approved sandbox for untrusted contributor refs.
3. For trusted work, fetch the base and create an isolated worktree. Never edit
   the primary checkout through a background worker.
4. Record the start SHA and include it, the worktree, branch, constraints, and
   required validation in the prompt.

For scratch Codex work, create a temporary directory and initialize Git first.

## Write the prompt

Put the complete task in a file. Include:

- intended outcome and in/out of scope;
- exact repository/worktree and starting SHA;
- files or interfaces that must not change;
- required tests and proof;
- whether commit, push, PR, or external writes are authorized;
- instruction to finish with a concise result and failure reason.

Do not put secrets or internal authentication instructions in the prompt.

## Start

```bash
SKILL_DIR=/path/to/coding-agent

bash "$SKILL_DIR/scripts/coding-agent-run" start \
  --agent auto \
  --workdir /path/to/isolated-worktree \
  --prompt-file /path/to/prompt.txt
```

The command returns `session_id`, selected `agent`, PID, and log path. It copies
the prompt into the session directory before launching.

Default provider modes do not bypass permissions. Only pass `--unsafe` when the
user explicitly authorizes bypass and the worktree is trusted and externally
sandboxed:

```bash
bash "$SKILL_DIR/scripts/coding-agent-run" start \
  --agent claude \
  --workdir /path/to/worktree \
  --prompt-file /path/to/prompt.txt \
  --unsafe
```

## Monitor

```bash
bash "$SKILL_DIR/scripts/coding-agent-run" status <session>
bash "$SKILL_DIR/scripts/coding-agent-run" log <session>
bash "$SKILL_DIR/scripts/coding-agent-run" wait <session> --timeout 900
bash "$SKILL_DIR/scripts/coding-agent-run" stop <session>
```

Set `CODING_AGENT_STATE_DIR` or pass `--state-dir DIR` to choose the session
store. Otherwise the runner uses `$XDG_STATE_HOME/coding-agent` or
`~/.local/state/coding-agent`.

Update the user after launch with the session ID and worktree. During execution,
report only milestones, questions, failures, user action, and completion.

## Verify the result

1. Inspect worker exit status and logs.
2. Review the diff; do not trust a success exit code alone.
3. Run the repository's relevant checks from the parent agent.
4. Refresh the target base and verify ancestry before pushing a new branch.
5. Never force-push or rewrite an existing/shared branch without explicit
   authorization.

## Provider references

- [Codex CLI](references/codex.md)
- [Claude Code](references/claude-code.md)
- [TClaude](references/tclaude.md)
- [OpenCode](references/opencode.md)
