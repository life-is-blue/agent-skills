# Codex CLI behavior

Verified locally on 2026-07-26 with `codex-cli 0.145.0`. Re-verify with
`codex --help`, `codex exec --help`, `codex exec resume --help`, and
`codex exec review --help` after a CLI upgrade; argument placement is
version-sensitive.

## Global options carry the run policy

`-C/--cd`, `-s/--sandbox`, `-a/--ask-for-approval`, `-m/--model`, and `-c` are
**global** options and must precede the subcommand. Placing them after `exec`
fails with `error: unexpected argument`.

`codex exec resume` and `codex exec review` do **not** accept `-C` or `-s` of
their own, which is why the adapter always builds:

```bash
codex -C <workdir> -s <sandbox> -a never [-m MODEL] [-c model_reasoning_effort="<effort>"] exec ...
```

`--strict-config` accepts `model_reasoning_effort`, confirming the key name.

## Subcommand shapes the adapter emits

| Kind | Command |
|---|---|
| task | `codex <globals> exec --json -o FINAL [--output-schema S] -` |
| resume | `codex <globals> exec resume <THREAD_ID> --json -o FINAL -` |
| review | `codex <globals> exec review --json -o FINAL [--uncommitted\|--base REF\|--commit SHA] [-]` |

The trailing `-` makes Codex read the prompt from stdin, which avoids argument
length and quoting limits. The adapter always supplies stdin explicitly
(prompt bytes or `/dev/null`); otherwise Codex prints
`Reading additional input from stdin...` and can block.

`codex exec resume --last` is not used. `--last` leaves the `[SESSION_ID]`
positional open, so a `-` prompt marker would be parsed as the session id.
The adapter resolves the newest thread id from its own job records and passes
it explicitly.

## Event stream

`--json` writes JSONL to stdout. Observed event types:

```jsonl
{"type":"thread.started","thread_id":"019f9e93-..."}
{"type":"turn.started"}
{"type":"item.completed","item":{"type":"file_change","changes":[{"path":"...","kind":"add"}],"status":"completed"}}
{"type":"item.completed","item":{"type":"command_execution","command":"/bin/bash -lc 'cat b.txt'","exit_code":0}}
{"type":"item.completed","item":{"type":"agent_message","text":"DONE"}}
{"type":"turn.completed","usage":{"input_tokens":13063,"cached_input_tokens":11008,"output_tokens":7}}
```

`-o/--output-last-message FILE` writes the final assistant message to disk; the
adapter prefers that file and falls back to the last `agent_message` event.
Unknown event types are ignored, so a newer CLI cannot break the reducer.

## Git requirement

Codex refuses to run outside a Git repository unless `--skip-git-repo-check` is
passed. The adapter intentionally does not pass it and fails with `E_INPUT`
before launching Codex.

## Not used by this adapter

`codex app-server` exposes a JSON-RPC protocol with a shared runtime,
`turn/interrupt`, thread listing, and reasoning summaries. It requires a
long-lived broker process and host session lifecycle hooks, so this adapter
stays on `codex exec --json`. The cost is a fresh process per run (a few
seconds) and SIGTERM-based cancellation instead of a graceful turn interrupt.
