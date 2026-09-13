# agy structured adapter

Requires Python 3 and an installed, authorized `agy` CLI. Check local
`agy --help` after upgrades; coordinator dispatch checks stream, schema and
sandbox flag availability without making a model call. Runtime compatibility
is covered by offline protocol fixtures, not a live-provider smoke.

```bash
python3 /path/to/coding-agent/scripts/codex_run.py start --agent agy --write \
  --workdir /path/to/worktree --prompt-file /path/to/contract.txt \
  --output-schema /path/to/schema.json --state-dir /approved/private/state \
  --job-id unique-attempt-id --timeout 3600 --json
```

The shared runner uses stream-json input/output, sends one `user` message and
closes stdin. It captures `conversation_id` and terminal `result`, exposing
`structured_output` in the envelope. Exit zero without a SUCCESS result is a
failure (including a CLI soft timeout returning partial output). The adapter
uses `--sandbox --mode accept-edits`; these flags do not imply that every
command is approved. Never bypass permissions to make a gate pass.

The adapter forwards explicit `--model` and `--effort` (low/medium/high). Setup
recommends a user-confirmed Gemini Flash 3.8-or-newer Flash ID with `high`;
that family/version requirement is not itself a CLI ID or an availability claim.

Only modifying tasks are supported. Plan mode is not an enforced read-only
boundary; use an authorized read-only reviewer instead. `--unsafe` and
`--resume-last` are refused. Explicit `--resume` maps to `--conversation` and
starts a new provider turn; it is not a status query. Before resuming, verify
the original job is terminal and the workspace/candidate still match.

`status`, `result`, `logs`, `wait` and `cancel` inspect/control local jobs without
starting a provider turn. Existing explicit job IDs are refused. `wait` timeout
does not cancel the execution or extend its execution timeout (agy defaults to
3600 seconds in the runner). Keep prompts,
events and stderr in approved private state, especially for withheld review.

Compare two status snapshots: `activity` separates bytes/mtime, text updates,
tool updates and local process presence. Text updates are not proof of tool
progress; tool updates are not proof of successful verification. For a claimed
browser/background job, corroborate the specific PID, port and expected artifact
change. Near-zero CPU or unchanged files alone only suggest a stall. Stop at
the execution bound or after diagnosing a stall; local process-group cancellation
does not prove detached/remote sidecars have stopped. Unknown/lost jobs must be
reconciled before reissuing a contract.

For local diagnosis (inspect the claimed child PID too), repeat these over the
observation interval and compare cumulative `TIME`, event bytes and artifacts:

```bash
ps -p "$WORKER_PID" -o pid,ppid,etime,time,state
lsof -nP -a -p "$CLAIMED_CHILD_PID" -iTCP
ls -l "$EXPECTED_ARTIFACT"
```

`ps` CPU time is cumulative, not elapsed wall time; absent listeners or artifact
changes matter only if the task actually promised them. A remote browser or
blocked external request needs its own evidence, not a local-CPU inference.

Protocol reference: [official headless documentation](https://antigravity.google/docs/cli/headless/).
CLI timeout changes: [official changelog](https://antigravity.google/changelog).
Flags inspected locally on 2026-09-13; no paid smoke was performed.

Workspace adaptation rechecked with local help on 2026-09-14: launch cwd is the
execution root; `--project` selects an agy project, not a verified Git worktree.
The runner does not use `--add-dir`, `--new-project` or implicit conversation
continuation to bridge checkouts. Coordinator native-job status validates the
recorded worker root separately from the control ledger root.
