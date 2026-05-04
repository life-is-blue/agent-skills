# Gemini headless mode — output and error handling

Reference for `gemini -p "..." -o json` as used by `scripts/gemini-summon.sh`.

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
| `-o json` | Structured JSON output. |
| `--yolo` (`-y`) | Auto-approve all tool actions. Default in this skill (CSS edits are reversible). |
| `--approval-mode plan` | Read-only; Gemini won't write. The wrapper uses `--read-only` to flip to this behavior (currently by dropping `--yolo`; switch to `--approval-mode plan` if you want strict read-only enforcement). |
| `-m <model>` | Override default model. Wrapper passes through `--model`. |
| `--include-directories` | Add extra workspace dirs. Not used by default — wrapper `cd`s into `--target`. |

## Expected JSON shape

The CLI help does not formally document the schema, so the wrapper is **defensive**. It tries common field names in this order:

1. `.response` — Gemini's natural-language reply.
2. `.text` — fallback name.
3. `.output` — fallback name.

If none parse, the wrapper prints raw stdout under the same `---` divider. This means the SKILL keeps working even if Gemini changes the JSON shape across versions. When in doubt, run with `--raw` to see exactly what Gemini emitted.

For errors:
- `.error` (string) → wrapper exits 1 and surfaces it on stderr.
- Non-zero CLI exit code → wrapper forwards it (124 for timeout, otherwise pass-through).

## Exit codes

| Code | Meaning | Wrapper response |
|---|---|---|
| 0 | Success | Print summary on stdout. |
| 1 | Gemini reported `.error` | Surface error on stderr. |
| 2 | Bad arguments to wrapper | Print usage. |
| 124 | `timeout` killed Gemini | Tell user the timeout. |
| 127 | `gemini` not on PATH | Print install instructions. |
| other | Gemini CLI failure | Pass through with stderr dump. |

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
