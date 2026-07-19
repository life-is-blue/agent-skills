# Gemini headless mode — output and error handling

Reference for `gemini -p "..." -o json` as used by `scripts/gemini-summon.sh`.
The flag surface was checked locally with Gemini CLI 0.40.1 on 2026-07-19.

## Why headless

`gemini -p` runs Gemini in non-interactive mode: one prompt in, one structured response out. Compared to the interactive REPL it gives:

- A clean exit code we can branch on.
- A structured JSON payload (`-o json`) instead of TTY-formatted text.
- No prompts for confirmation when paired with `--yolo`.
- Stdin can be piped in (the `-p` text is appended), useful for very long context.

Reference docs: <https://geminicli.com/docs/cli/headless/>

## CLI flags the wrapper uses

| Flag | Purpose |
|---|---|
| `-p, --prompt <text>` | The headless prompt. |
| `-o json` | Single structured JSON object (one shot). |
| `-o stream-json` | NDJSON event stream — what the wrapper's `--stream` mode uses. |
| `--yolo` (`-y`) | Auto-approve all tool actions. Default in this skill (CSS edits are reversible). |
| `--approval-mode plan` | Strict read-only mode used by the wrapper's `--read-only` flag. |
| `-m <model>` | Override default model. Wrapper passes through `--model`. |
| `--include-directories` | Add extra workspace dirs. Not used by default — wrapper `cd`s into `--target`. |

## Output shapes

### `-o json` (default, single object)

The CLI help does not formally document the schema, so the wrapper is **defensive**. It tries common field names in this order:

1. `.response` — Gemini's natural-language reply.
2. `.text` — fallback name.
3. `.output` — fallback name.

If none parse, the wrapper prints raw stdout under the same `---` divider. When in doubt, run with `--raw` to see exactly what Gemini emitted.

Error surface:
- `.error` (string) → wrapper exits 1 and surfaces it on stderr.

### `-o stream-json` (used by `--stream`)

Newline-delimited JSON. Every line is one event object. The five event types
below were observed with Gemini CLI 0.37. A live 0.40.1 schema smoke could not
be completed in the 2026-07-19 validation environment, so the wrapper continues
to parse defensively rather than claiming the shape is stable.

| `type` | Key fields | Emitted when |
|---|---|---|
| `init` | `session_id`, `model` | Session starts |
| `message` | `role` (user/assistant), `content`, `delta` (bool) | User prompt and every assistant text chunk |
| `tool_use` | `tool_name`, `tool_id`, `parameters` | Gemini decides to call a tool |
| `tool_result` | `tool_id`, `status`, `output?` | Each `tool_use` resolves |
| `result` | `status`, `stats.{total_tokens, tool_calls, duration_ms, models}` | Final event, run is done |

`error` is also listed in the official docs but was not observed in smoke tests — the wrapper's `fmt_stream_line` handles it defensively.

The wrapper:
- Tees the full NDJSON to `/tmp/gemini-summon-<ts>-<pid>.ndjson` (inspectable afterwards via `--status` / `--follow`).
- Formats each event into a one-line stderr timeline so the caller sees `update_topic → write_file (hello.html) → success → done: tools=3 tokens=...`.
- Reconstructs the final assistant message by concatenating `message` events where `role=="assistant"`.
- Reports `tools=N edits=M` in the summary header, where `edits` counts `tool_use` events whose `tool_name` matches `write_file|replace|edit`.

Assistant messages arrive as `delta: true` chunks — the wrapper's jq filter joins them back into a single response string.

## Exit codes

| Code | Meaning | Wrapper response |
|---|---|---|
| 0 | Success | Print summary on stdout. |
| 1 | Gemini reported `.error` in JSON payload | Surface error on stderr. |
| 2 | Bad arguments to wrapper | Print usage. |
| 42 | Gemini rejected input (invalid prompt/args) | Targeted stderr message + pass through. |
| 53 | Gemini hit turn limit | Suggest breaking the task up + pass through. |
| 55 | Untrusted workspace | Explain + point at `GEMINI_CLI_TRUST_WORKSPACE`. |
| 124 | `timeout` killed Gemini | Tell user the timeout; for `--stream` runs also point at the partial session file. |
| 127 | `gemini` not on PATH | Print install instructions. |
| other | Gemini CLI failure | Pass through with stderr dump. |

The wrapper exports `GEMINI_CLI_TRUST_WORKSPACE=true` by default (Gemini 0.40+ refuses to run in untrusted dirs). Caller can override by exporting `=false`.

## Multimodal references

Gemini's prompt syntax includes `@path` for file/image references — the file at that path is attached to the prompt. The wrapper translates `--ref a.png --ref b.png` into `@<abs-path-a> @<abs-path-b>` appended after the brief.

Use absolute paths (the wrapper resolves them) because the wrapper `cd`s into `--target` before calling Gemini, and relative refs would otherwise resolve from the wrong dir.

## Stdin piping (advanced, not used by default)

For extremely long context (e.g., one giant file Gemini should read), `gemini -p "..."` accepts stdin and prepends it to the prompt:

```bash
cat huge-component.tsx | gemini -p "Refactor this for responsive layout" --yolo -o json
```

The wrapper does **not** auto-pipe — `@path` references are usually cleaner. If you need this pattern, call gemini directly rather than extending the wrapper; one-off plumbing doesn't deserve a flag.

## Resume / sessions

`gemini --resume latest` continues the previous session. The wrapper does not expose this — front-end iterations should be one-shot per user turn (return to the user, get the next brief, fire fresh). If you need persistent multi-turn, that's a sign the work belongs in a subagent, not this wrapper.
