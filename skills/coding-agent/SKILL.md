---
name: coding-agent
description: Delegate substantial coding work to Codex, Claude Code, TClaude, CodeBuddy Code, or OpenCode through a portable monitored background runner. Use for feature implementation, large refactors, code reviews, and long issue-to-PR work; do not use for simple edits, read-only lookup, or tasks that must remain in the current agent thread.
---

# Coding Agent

Use the bundled `scripts/coding-agent-run` adapter to launch and monitor coding
CLIs without depending on OpenClaw.

## Route

- Honor an explicitly requested provider.
- With `--agent auto`, select the first installed provider in this order:
  Codex, Claude Code, TClaude, CodeBuddy Code, OpenCode.
- Use the `codex-delegate` Skill instead when the work is Codex-specific and
  the caller needs provider event parsing, thread resume, output-schema parsing,
  or the built-in reviewer. This runner keeps provider output as a plain log.
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

For a machine-consumed workflow, also declare a result path inside the worktree
and the JSON contract the worker must write there. The runner checks the file as
an artifact; it does not infer a result by parsing provider prose.

Do not put secrets or internal authentication instructions in the prompt.

## Start

```bash
SKILL_DIR=/path/to/coding-agent

bash "$SKILL_DIR/scripts/coding-agent-run" start \
  --agent auto \
  --workdir /path/to/isolated-worktree \
  --prompt-file /path/to/prompt.txt \
  --result-file .verified-dev-loop/run-1/deliveries/round-1.json \
  --json
```

Without `--json`, the command returns the existing compact text containing
`session_id`, selected `agent`, PID, and log path. With `--json`, it returns the
versioned transport envelope described below. The runner copies the prompt into
the session directory before launching.

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

Add `--json` to `status`, `wait`, or `stop` when the caller consumes structured
state. `log` always returns the raw combined provider output.

Set `CODING_AGENT_STATE_DIR` or pass `--state-dir DIR` to choose the session
store. Otherwise the runner uses `$XDG_STATE_HOME/coding-agent` or
`~/.local/state/coding-agent`.

Update the user after launch with the session ID and worktree. During execution,
report only milestones, questions, failures, user action, and completion.

## Transport envelope and result artifact

JSON output has this stable shape:

```json
{
  "schema_version": 1,
  "session_id": "20260830T120000Z-123-456",
  "status": "completed",
  "agent": "codex",
  "pid": 123,
  "workdir": "/path/to/worktree",
  "unsafe": false,
  "worker_exit_code": 0,
  "started_at": "2026-08-30T12:00:00Z",
  "finished_at": "2026-08-30T12:01:00Z",
  "log_file": "/state/sessions/<id>/output.log",
  "result_artifact": {
    "required": true,
    "path": "/path/to/worktree/delivery.json",
    "status": "present",
    "bytes": 128,
    "sha256": "..."
  },
  "wait_timed_out": false,
  "errors": []
}
```

Transport `status` is `running`, `stopping`, `completed`, `failed`, `cancelled`,
or `lost`.
Artifact status is independently `not-requested`, `pending`, `present`,
`missing`, `invalid`, `outside-workdir`, or `too-large`. `wait --timeout` leaves
the job running, sets `wait_timed_out`, and exits 124. When the worker exits zero
but a required artifact is missing or unsafe, `wait` exits 2 while preserving
the worker exit code in the envelope.

`--result-file` accepts only a relative path inside the worktree. At terminal
state the runner requires a regular file, rejects symlink escape, and records its
size and SHA-256. It refuses a path that already exists at dispatch so stale
output cannot satisfy a new run, and rejects existing parent links that escape
the real worktree. Result envelopes are limited to 1 MiB and hashed as a stream.
The runner intentionally does not parse or validate their contents; the calling
protocol owns that schema and acceptance decision.

`stop` records an explicit cancellation request before signaling the wrapper and
provider. Until both finish, status remains `stopping`; only a terminal exit 143
associated with that request becomes `cancelled`. A provider that exits 143 on
its own is `failed`.

The base text-mode runner needs Bash and ordinary POSIX process tools. `--json`
and `--result-file` additionally require Python 3 from the host.

## Verify the result

1. Inspect worker exit status and logs.
2. If a result artifact was required, verify its envelope and parse it against
   the calling protocol; transport success is not acceptance.
3. Review the diff; do not trust a success exit code alone.
4. Run the repository's relevant checks from the parent agent.
5. Refresh the target base and verify ancestry before pushing a new branch.
6. Never force-push or rewrite an existing/shared branch without explicit
   authorization.

## Provider references

- [Codex CLI](references/codex.md)
- [Claude Code](references/claude-code.md)
- [TClaude](references/tclaude.md)
- [CodeBuddy Code](references/codebuddy.md)
- [OpenCode](references/opencode.md)
