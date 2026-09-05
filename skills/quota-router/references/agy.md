# agy (Antigravity CLI)

Verified locally with agy 1.1.19 via `agy --help` plus real invocations,
cross-checked against `~/.gemini/antigravity-cli/settings.json` behavior.

## Read-only invocation

```bash
agy -p "<prompt>" --output-format json --print-timeout <duration>
```

`--print-timeout` is a native timeout flag; agy is the only one of the three
CLIs that has one. `--output-format` accepts `text`/`json`/`stream-json`.

## Envelope and success criterion

Single JSON object. Parse it and require `status` to be `"SUCCESS"` and
`response` to be non-empty; capture `conversation_id` for resume.

```json
{"status":"SUCCESS","response":"...","conversation_id":"..."}
```

**agy gives JSON on failure too** (the opposite of Cursor and CodeBuddy): a
failed run can still exit 0 with `status:"ERROR"` and an error message in
`response`. Never treat exit 0 alone as success.

## Read-only boundary

Run from a directory listed in agy's `trustedWorkspaces`. Outside a trusted
workspace, even reads are auto-denied: exit 0, `status:"CANCELED"`, empty
`response`, and a plain-English refusal on stderr. Remedy: run agy
interactively once from that directory to grant trust, or add the directory
under `trustedWorkspaces` in `~/.gemini/antigravity-cli/settings.json`.

## Write path: broken by design, use apply mode instead

Two permission tiers were tested against a real user file and neither writes
it:

- Default (no flag): `status:"CANCELED"`, file untouched. Clean refusal:
  stderr says the write tool needs command-level approval, headless mode
  cannot prompt for it, and the call is auto-denied.
- `--dangerously-skip-permissions`: `status:"ERROR"`, file still untouched —
  agy's write tool is hardcoded to only accept paths under
  `~/.gemini/antigravity-cli/brain/<conversation-id>/`. **`response` still
  contains the fully modified file content agy intended to write.** Do not
  mistake this for a successful edit; it is a fake-success shape (see
  [known-failure-modes.md](known-failure-modes.md)).

There is no `--allowed-tools` or equivalent flag; the CLI only has these two
tiers. Do not ask agy to write a user file directly.

**Apply mode is the viable write path.** When the working directory is
already in `trustedWorkspaces` and the prompt explicitly asks agy to output
the changed content rather than modify files, the default permission tier
returns `status:"SUCCESS"` with the complete, correct modified file content in
`response`, and the original file is untouched (`read_file` is
auto-allowed inside a trusted workspace, so no flag is needed). The calling
agent must show that content to the user and write it only after the user
confirms — the markdown-fence format of the response is not guaranteed
stable and this Skill does not parse it.

## Resume

Add `--conversation <conversation_id>`. On a bad or stale id, agy still
returns exit 0 and `status:"SUCCESS"`, but with an **empty `response`**, a
**newly assigned `conversation_id`**, and a one-line refusal on stderr
("conversation not found"). Always compare the returned `conversation_id`
to the one you requested; a mismatch means the context was not continued.

## Viewing images

Name the image file in the prompt **and explicitly ask agy to use the
`view_file` tool** — e.g. `agy -p "Use the view_file tool to read
<path>, then describe ..."`. Both absolute and workspace-relative paths work;
`view_file` is not gated by command-level permission.

- Naming only the file path, without asking for `view_file`, reaches a
  different, permission-gated read path: headless mode auto-denies it and the
  call returns exit 0, `status:"SUCCESS"`, **empty `response`**, with only a
  stderr `auto-denied` warning — another fake-success shape.
- `--input-format stream-json` does not accept an `image` content block; only
  `text` blocks are supported over that channel.
- `-p` followed directly by another flag swallows that flag as part of the
  prompt text. When combining `-p` with other flags, use the `-p=` form.
