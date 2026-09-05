# CodeBuddy Code (headless research use)

Verified locally with CodeBuddy Code 2.137.1 via `codebuddy --help`, the
`codebuddy-docs` knowledge base (`headless.md`, `cli-reference.md`,
`permission-modes.md`), and real invocations. This reference covers
read-only research invocation; see the `coding-agent` Skill's own CodeBuddy
reference for its role as a full write-capable coding agent.

CodeBuddy is a fork of Claude Code and its flags look nearly identical
(`-p`, `--output-format`, `--resume`, `--permission-mode`, `--allowedTools`).
**That resemblance is the trap** — its output shape and exit-code semantics
differ from both Claude Code's usual contract and from agy/Cursor.

## Read-only invocation

```bash
codebuddy -p "<prompt>" --permission-mode dontAsk --tools Read,Glob,Grep --output-format json
```

`--permission-mode dontAsk` is CodeBuddy's own recommendation for
non-interactive automation and is stricter than it sounds ("don't prompt,
just refuse anything not pre-approved"). Combine it with an explicit
`--tools` whitelist for a second, independent layer: `--tools Read,Glob,Grep`
removes write tools at the tool level regardless of permission-mode
semantics. **Never pass `-y`/`--dangerously-skip-permissions`** for research;
CodeBuddy's docs describe it as required for write/command automation, and
passing it for read-only work removes every guard at once.

`--permission-mode plan` looks read-only but is not a clean choice here: it
delegates its read/write boundary to whatever mode preceded it, and it writes
its own plan file under `~/.codebuddy/plans/` as a side effect.

## Envelope: stdout is a JSON array, not an object

This is the largest difference from the other two CLIs. `--output-format
json` prints the **entire transcript as a JSON array** (length varies with
turn count and tool calls; a plain answer is 4-5 elements, a
tool-using research call can be 12+). The result you want is the array
element whose `type` is `"result"`:

```json
{"type":"result","subtype":"success","is_error":false,"result":"...","session_id":"...",
 "usage":{"input_tokens":0,"output_tokens":0},"permission_denials":[]}
```

`JSON.parse(stdout)` yields an array, not an object — `.result` on it is
`undefined`. Use `Array.isArray()` then `find(x => x.type === "result")`.
Do not assume the result element is the last one; find it by `type`.

Field names: response text is `result` (matches Cursor, not agy's
`response`); session id is `session_id` (matches Cursor); `usage` is
snake_case (matches agy, not Cursor's camelCase). Each of the three CLIs
uses a different combination of these four field conventions — no pairwise
parser reuse is safe.

Stdout is also noticeably larger than the other two CLIs: even a one-line
answer can be 17-18KB because the full system prompt is echoed back inside
the first `message` element of the array. Do not log or store the whole
array; extract only the `result` element.

## Exit code is not trustworthy

Two failure shapes were observed with different exit codes:

| Failure | exit | stdout | stderr |
| --- | --- | --- | --- |
| Unknown model name (API-layer failure) | **0** | 0 bytes | plain text error + available-model list |
| Unknown flag (argument-layer failure) | 1 | 0 bytes | `error: unknown option '...'` |

The API-layer failure reproduced on repeated tries at exit 0. **The only
reliable success criterion is "stdout parses as an array and contains an
element with `type:"result"` and a non-empty `result` field."** A rule like
"exit 0 and non-empty stdout" (which is sufficient for Cursor) is not
sufficient here and will misclassify an API failure as success.

`is_error` and `permission_denials` are both hollow fields: they were `false`
and `[]` respectively even in a run where a write was actually denied by
`--permission-mode plan`. The refusal only appeared in the natural-language
`result` text, in Chinese ("被拒绝", "禁止", "无法完成") — CodeBuddy's
responses are Chinese-heavy, and Cursor's English refusal keyword list does
not transfer.

## No native timeout

No `--timeout` flag exists; wrap the process with an external timeout
(`setTimeout` + `SIGTERM` then `SIGKILL`). `--max-turns <n>` is a turn-count
brake, not a time brake — useful as an additional guard but not a substitute.

## Background mode (`--bg`) is broken — do not use

CodeBuddy is the only one of the three CLIs with a native background mode
(`--bg --name <name>`, plus `codebuddy ps` / `logs` / `kill`). On version
2.137.1 it is **functionally broken**: two independent probes showed the job
accepted and the model finishing in ~1.2s, but the assistant's reply never
lands in the transcript, the target file is never modified, and the session
spins forever with no further activity. The log path printed at startup
(`~/.codebuddy/logs/{name}.log`) also stays at 0 bytes; real output goes to a
dated directory instead. Do not build on `--bg` until this is retested after
a CodeBuddy upgrade. Synchronous mode (`-p`) is unaffected.

## Readiness probe

`codebuddy --version` is safe (clean, fast, non-empty output means it is
installed). **Do not use anything else to probe readiness or login state**:
`status`, `whoami`, a bare invocation, and any unrecognized flag are all sent
to the model as a real prompt and consume a genuine turn — CodeBuddy has no
side-effect-free way to check login state. Report login state as "unknown"
rather than guessing.
