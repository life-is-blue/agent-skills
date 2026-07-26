# Result contract

`start`, `review`, `status <job>`, `result`, `wait`, and `cancel` all print the
same envelope. With `--json` it is a single JSON object; without it, a compact
text rendering of the same fields.

## Envelope

```json
{
  "schema_version": 1,
  "job_id": "task-20260726T132852Z-769470",
  "job_dir": "/state/jobs/task-20260726T132852Z-769470",
  "kind": "task",
  "status": "completed",
  "phase": "done",
  "exit_code": 0,
  "codex_exit_code": 0,
  "workdir": "/path/to/worktree",
  "sandbox": "workspace-write",
  "model": null,
  "effort": null,
  "output_schema": null,
  "resume_thread_id": null,
  "review_target": null,
  "timeout_seconds": null,
  "has_prompt": true,
  "prompt_chars": 812,
  "created_at": "2026-07-26T13:28:52Z",
  "started_at": "2026-07-26T13:28:52Z",
  "finished_at": "2026-07-26T13:31:04Z",
  "duration_ms": 132145,
  "pid": null,
  "child_pid": null,
  "command": ["codex", "-C", "...", "exec", "--json", "-o", "...", "-"],
  "thread_id": "019f9e93-4c66-7702-9d9e-8496fe643b3e",
  "resume_command": "codex exec resume 019f9e93-4c66-7702-9d9e-8496fe643b3e",
  "final_message": "...",
  "structured_output": null,
  "touched_files": [{"path": "/path/to/worktree/src/a.py", "kind": "add"}],
  "commands": [{"command": "pytest -q", "exit_code": 0, "status": "completed"}],
  "usage": {"input_tokens": 13063, "cached_input_tokens": 11008, "output_tokens": 7},
  "agent_messages": 3,
  "errors": [],
  "events_file": "/state/jobs/<id>/events.jsonl",
  "log_file": "/state/jobs/<id>/stderr.log"
}
```

Field notes:

- `kind` is `task`, `resume`, or `review`. Passing `--resume`/`--resume-last`
  turns a `start` into a `resume` job.
- `status` is `queued`, `running`, `completed`, `failed`, `cancelled`,
  `timeout`, or `lost`. `lost` means the recorded worker pid is gone without a
  terminal record.
- `phase` is a coarse progress hint derived from the live event stream
  (`starting`, `investigating`, `editing`, `running`, `done`, `failed`). It is
  usable while the job is still running.
- `exit_code` is the adapter's code; `codex_exit_code` is the raw CLI code.
- `structured_output` is the parsed `final_message` and is only populated when
  `--output-schema` was supplied and the message parses as JSON.
- `touched_files` and `commands` come from completed event items, so an
  interrupted job reports what Codex had finished at that point.
- `errors` merges adapter errors with `error` and `turn.failed` events.

`status` without a job id prints a job list instead:

```json
{"schema_version": 1, "state_dir": "...", "jobs": [{"job_id": "...", "kind": "task", "status": "completed", "phase": "done", "workdir": "...", "thread_id": "...", "created_at": "..."}]}
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | job completed, or the command only reported state |
| 1 | `E_INPUT` on stderr: bad arguments, missing prompt, no Git repository, unknown job |
| 2 | Codex ran and failed, or the job is `failed`/`lost` |
| 124 | the job hit `--timeout`, or `wait --timeout` expired first |
| 143 | the job was cancelled |

`wait --timeout` expiring sets `wait_timed_out` in the envelope and leaves the
job running; it does not cancel anything.

## Job directory

Each job owns `<state-dir>/jobs/<job-id>/`:

| File | Content |
|---|---|
| `job.json` | the stored envelope, rewritten at each state change |
| `prompt.txt` | the exact prompt sent to Codex |
| `events.jsonl` | the raw `codex exec --json` stream |
| `final.txt` | the final assistant message from `-o` |
| `stderr.log` | Codex stderr |
| `worker.log` | background worker output, only for `--background` |

Nothing is pruned automatically. Delete old job directories when the state
directory grows.
