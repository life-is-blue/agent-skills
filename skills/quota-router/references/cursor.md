# Cursor CLI (`agent`)

Verified locally with Cursor CLI 2026.08.11-e8db854 via `agent --help`, the
official `cli/reference/output-format.md` and `cli/reference/parameters.md`,
and real invocations. The binary is `agent`; `cursor-agent`/`cursor` are
aliases of the same binary.

## Read-only invocation

```bash
agent -p "<prompt>" --output-format json --mode ask
```

`-p`/`--print` runs non-interactively. Unlike agy, Cursor's default tool
permissions are wide open (it can write files and run shell commands without
extra flags), so read-only research should always pass `--mode ask`
("explore code without making changes") rather than relying on the absence
of `--force` as the only guard.

## Envelope and success criterion

Single JSON object, but the field names do not match agy's:

```json
{"type":"result","subtype":"success","is_error":false,"result":"...","session_id":"...","request_id":"...","usage":{"inputTokens":0,"outputTokens":0}}
```

Response text is `result` (not `response`), session id is `session_id` (not
`conversation_id`), and `usage` uses camelCase field names (not snake_case).
Copying agy's field names here will silently read `undefined`.

## Hard failure gives no JSON at all

This is the opposite of agy and is documented Cursor behavior, not an
observation gap: on failure the process exits non-zero, stdout is empty (0
bytes), and the error message is plain text on stderr. **Check exit code and
non-empty stdout before attempting to parse JSON.** `is_error` only ever
appears in the success envelope and is documented as always `false` there —
it carries no information and must not be used as a success signal.

## Refusal signal is natural-language, not structured

When a shell command Cursor tries to run is denied by the environment, Cursor
does not hang or hard-fail: it retries, then writes a sentence like "this
command was blocked by the environment" into `result` and still returns
`is_error:false`, exit 0. There is no clean stderr keyword like agy has;
scanning must fall back to English refusal words in `result`
(`blocked`/`rejected`, etc.).

## No native timeout

`agent --help` and the official parameter reference have no `--timeout` or
equivalent for a `-p` invocation (`agent worker --idle-release-timeout` is an
unrelated cloud-worker setting). Wrap the process with an external timeout
(`spawn` + `setTimeout` + `SIGTERM`).

## Write path

### The real gate is Workspace Trust, not `--force`

Without `--trust`/`--force`/`--yolo`, a write attempt fails with exit 1, empty
stdout, and this stderr:

```
⚠ Workspace Trust Required
  Cursor Agent can execute code and access files in this directory.
  Do you trust the contents of this directory?
    <path>
  To proceed, you can either:
    • Run 'agent' interactively to decide
    • Pass --trust, --yolo, or -f if you trust this directory
```

This is a directory-level gate, separate from any individual tool-call
approval. Any of `--trust`, `--yolo`, `-f`/`--force` opens it.
**`--trust` alone is sufficient to edit files** — it does not also open the
"auto-approve shell commands" gate that `--force`/`--yolo` open, so prefer it
for edit-only work. Always surface this stderr text to the user on failure;
reporting only "exit 1" leaves them guessing which flag to add.

### No change list in the JSON, ever

The write-path envelope has exactly the same top-level keys as the read-only
one. There is no `files_changed`, no diff, nothing structured — which files
changed is only described in the natural-language `result` text. Verify
writes by checking the filesystem (git status / hash comparison), not by
trusting the envelope.

### The real trap: partial success on a `--trust`-only run

With `--trust` alone, a task requiring a shell command (e.g. "run a command
and append its output to a file") can produce: exit 0, `is_error:false`, the
file genuinely modified, empty stderr — but `result` states the shell tool
call was refused and the value it wrote was computed rather than executed.

This defeats every structural check at once: the file hash changed, so a
disk-diff check passes; exit code and `is_error` are clean; there is no
stderr. **The only tell is the refusal wording inside `result`, combined with
a description that does not match what was asked.** Never accept a Cursor
"verified"/"ran the tests" claim from `result` alone when the task required
running something — rerun it yourself.

## Resume

Add `--resume <session_id>`. On a bad id, Cursor **silently starts a brand
new conversation** — exit 0, well-formed success JSON, `subtype:"success"`,
no error signal of any kind. The only way to detect this is to compare the
returned `session_id` to the one you requested; a mismatch means the prior
context was lost, not continued.
