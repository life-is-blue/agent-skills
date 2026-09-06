---
name: coding-agent
description: Delegate substantial coding work to Codex, Claude Code, TClaude, CodeBuddy Code, or OpenCode through a portable monitored background runner, with a structured Codex mode that returns a machine-readable result envelope (thread id, touched files, token usage) and supports thread resume and a built-in reviewer. Use for feature implementation, large refactors, code reviews, and long issue-to-PR work; do not use for simple edits, read-only lookup, or tasks that must remain in the current agent thread.
---

# Coding Agent

This Skill bundles two adapters:

- `scripts/coding-agent-run` — the plain-log runner. Launches and monitors any
  supported coding CLI (Codex, Claude Code, TClaude, CodeBuddy Code, OpenCode)
  and keeps provider output as a plain log. Its sessions, commands, and
  transport envelope are documented in the sections marked *(plain-log
  runner)*.
- `scripts/codex_run.py` — the Codex structured mode. Codex-only; returns a
  machine-readable result envelope instead of a log. See the section marked
  *(structured mode)*.

The workspace, prompt, and verification sections apply to both adapters.

## Route

- Honor an explicitly requested provider.
- With `--agent auto`, select the first installed provider in this order:
  Codex, Claude Code, TClaude, CodeBuddy Code, OpenCode.
- Choose the Codex structured mode (`scripts/codex_run.py`) when the work is
  Codex-specific and the caller needs provider event parsing, thread resume,
  output-schema parsing, or the built-in reviewer. For everything else, use the
  plain-log runner (`scripts/coding-agent-run`).
- Handle simple edits and read-only questions directly.
- Do not silently switch an explicitly chosen provider after a failure.
  Diagnose first; retry with a relevant change, use an already-authorized
  fallback, or report the concrete blocker.

Read the matching provider reference before first use on a host or after a CLI
upgrade.

## Prepare the workspace

For a modifying task in Git:

1. Resolve the target repository, canonical remote, target base, and trust of
   the source ref from the request and Git state. Ask only about a material
   ambiguity that inspection cannot settle.
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

## Start (plain-log runner)

Use synchronous `run` when the host waits on one tool call or reaps background
processes after that call returns:

```bash
SKILL_DIR=/path/to/coding-agent

bash "$SKILL_DIR/scripts/coding-agent-run" run \
  --agent auto \
  --workdir /path/to/isolated-worktree \
  --prompt-file /path/to/prompt.txt \
  --result-file .coordinator/run-1/deliveries/round-1.json \
  --json
```

`run` returns one terminal envelope. Use asynchronous `start` only when the host
has verified that detached processes survive between calls:

```bash
SKILL_DIR=/path/to/coding-agent

bash "$SKILL_DIR/scripts/coding-agent-run" start \
  --agent auto \
  --workdir /path/to/isolated-worktree \
  --prompt-file /path/to/prompt.txt \
  --result-file .coordinator/run-1/deliveries/round-1.json \
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

## Monitor (plain-log runner)

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

## Transport envelope and result artifact (plain-log runner)

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

## Codex structured mode (codex_run.py)

`scripts/codex_run.py` executes the Codex CLI as a monitored job with a stable
JSON envelope (job id, thread id, touched files, executed commands, token
usage), thread resume, and an always-read-only built-in reviewer. Use it when a
calling agent must act on Codex's result programmatically.

```bash
SKILL_DIR=/path/to/coding-agent

python3 "$SKILL_DIR/scripts/codex_run.py" doctor
python3 "$SKILL_DIR/scripts/codex_run.py" start \
  --workdir /path/to/worktree --prompt-file /path/to/prompt.txt \
  --write --background --timeout 3600 --json
python3 "$SKILL_DIR/scripts/codex_run.py" wait <job-id> --timeout 900 --json
python3 "$SKILL_DIR/scripts/codex_run.py" review --workdir /path/to/repo --uncommitted --json
```

The full operational guide is
[Codex structured mode](references/codex-structured.md), with the envelope
schema in [codex-result-contract.md](references/codex-result-contract.md) and
the verified CLI behavior in [codex-cli.md](references/codex-cli.md).

## Provider references

- [Codex CLI behavior](references/codex-cli.md) — verified flags and event
  stream for both Codex adapters
- [Codex structured mode](references/codex-structured.md) — operations guide
  for `codex_run.py`
- [Claude Code](references/claude-code.md)
- [TClaude](references/tclaude.md)
- [CodeBuddy Code](references/codebuddy.md)
- [OpenCode](references/opencode.md)
