# Known failure modes across all three CLIs

The pattern that shows up repeatedly across agy, Cursor, and CodeBuddy: every
structured success signal these CLIs expose — exit code, a boolean `is_error`
field, a status enum, a "denials" array — has been observed being wrong on at
least one of them. The one signal that has not yet failed is the
natural-language text of the response itself. Always read it, in both English
and Chinese, before accepting a result as genuine.

## The four measured fake-success shapes

1. **agy write path.** With
   `--dangerously-skip-permissions`, agy's write tool refuses (it is
   hardcoded to a directory outside the target file) and returns
   `status:"ERROR"` — but `response` still contains the complete, correct
   modified file content it intended to write. An unattended consumer that
   only checks `status` would treat this as a hard failure and miss that the
   correct answer already exists in the response text. See
   [agy.md](agy.md).

2. **Cursor partial success on a write task requiring a shell command.**
   With only `--trust` passed, a task like "run a command and append its
   output to a file" can produce a genuinely modified file, exit 0,
   `is_error:false`, and empty stderr — while `result` states the shell call
   was refused and the value written was computed rather than executed. File
   hash, exit code, and `is_error` all agree it "worked"; only the
   natural-language text says otherwise. See [cursor.md](cursor.md).

3. **Resume onto a stale or invalid session/conversation id**, three
   different shapes, all exit 0:

   | Engine | Shape | How to detect |
   | --- | --- | --- |
   | agy | `status:"SUCCESS"`, but `response` is empty and a **new** `conversation_id` is assigned; one stderr warning line | Empty response + stderr keyword |
   | Cursor | Normal-looking success JSON; **silently starts a brand-new conversation** with no error signal | Only by comparing returned `session_id` to the requested id |
   | CodeBuddy | stdout is 0 bytes; stderr has plain text `No conversation found with session ID: ...` | Empty stdout, matches existing failure handling |

   Cursor's shape is the most dangerous of the three: nothing in the
   envelope indicates anything went wrong, and it can go on to answer as if
   the new, empty conversation were a continuation (e.g. reading the
   workspace to answer "continue"). **Always compare the returned id to the
   requested id after every resumed call**, for every engine.

4. **agy image viewing without naming the `view_file` tool.** Asking agy to
   describe an image by path alone (instead of explicitly requesting the
   `view_file` tool) routes through a different, command-permission-gated
   read path that headless mode auto-denies: exit 0, `status:"SUCCESS"`,
   **empty `response`**, with the only clue being an `auto-denied` warning on
   stderr. See [agy.md](agy.md).

## What this means for consuming any result

- A clean exit code proves the process terminated normally. It proves
  nothing about whether the requested action happened.
- A boolean or enum "success" field is not evidence on its own for any of
  these three CLIs — each has at least one documented case of that field
  being true/success while the actual output was empty, guessed, or absent.
- The structured "denial" fields (CodeBuddy's `permission_denials`) are
  known to stay empty even during a real denial. Do not treat an empty
  denial array as proof nothing was blocked.
- Scan the natural-language response for refusal wording in both languages:
  at minimum `blocked`, `rejected`, `denied`, `skipped`, `unable`, `被拒绝`,
  `禁止`, `跳过`, `无法`, `未能`. A hit that describes a third party inside
  the answer's own subject matter (for example, an answer about git
  behavior containing the phrase "Git 会拒绝") is not evidence of the CLI
  refusing your request — when genuinely ambiguous, surface the hit and its
  surrounding text to the user rather than deciding silently.
- For any task that required running a command or a test, do not accept the
  CLI's own claim that it did so. Rerun it yourself.
