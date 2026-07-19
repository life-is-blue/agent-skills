# Coding agent adapters

## Goal

Add two independently installable adapters: an OpenClaw-native coding-agent
workflow and a portable background coding-agent runner. Preserve the upstream
OpenClaw skill as an immutable, attributed reference.

## Decisions

- Classify both Skills as `adapter`.
- Snapshot OpenClaw `coding-agent/SKILL.md` at commit
  `4e0cc187a21cca36d1887998c101c6b9baf926be`; keep the snapshot unchanged and
  store the upstream MIT license beside it.
- Keep OpenClaw notification, process-session, and isolated-worktree semantics
  only in `openclaw-coding-agent`.
- Make `coding-agent` independent of OpenClaw. Ship a Bash runner with
  `start/status/log/wait/stop` actions and support `codex`, `claude`,
  `tclaude`, and `opencode`.
- Default to sandboxed/non-bypass provider modes. Require explicit `--unsafe`
  for provider permission bypass flags.
- Document only locally verified, portable `tclaude` CLI behavior; do
  not record internal URLs, credentials, authentication workflows, or company
  environment details.
- Do not run live model calls in automated tests. Test the runner with fake
  provider executables and isolated temporary state.

## Interfaces

```text
coding-agent-run start --agent <auto|codex|claude|tclaude|opencode> \
  --workdir DIR --prompt-file FILE [--state-dir DIR] [--unsafe]
coding-agent-run status SESSION [--state-dir DIR]
coding-agent-run log SESSION [--state-dir DIR]
coding-agent-run wait SESSION [--state-dir DIR]
coding-agent-run stop SESSION [--state-dir DIR]
```

`start` prints the session ID and log path. Provider output is written to a
per-session log. The session directory records the copied prompt, PID, selected
provider, workdir, start time, and final exit code.

## Acceptance

- Both Skill directories pass the repository contract and remain independently
  copyable.
- The OpenClaw snapshot matches the recorded upstream commit byte-for-byte.
- Auto-selection is deterministic and explicit agent selection fails clearly
  when the binary is unavailable.
- Runner lifecycle tests cover successful background execution, logs, status,
  wait, stop/error handling, and unsafe flag mapping without invoking a model.
- `python3 scripts/validate_repo.py` and `python3 -m pytest -q` pass.
