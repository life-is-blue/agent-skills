---
name: quota-router
description: Route research, documentation lookup, and small single-file edits to whichever cheap local CLI (Antigravity/agy, Cursor CLI, CodeBuddy Code) is actually installed, using each CLI's measured envelope and failure contract instead of a shared parser. Use when the user wants to save a more expensive model's quota on a quick lookup or small edit, or mentions agy, Cursor CLI/agent, or CodeBuddy headless calls; do not use for substantial coding work, multi-file changes, or monitored background delegation.
---

# Quota Router

Route only work the user has authorized to an available local CLI. These three
CLIs share superficially similar flags (`-p`, `--output-format json`,
`--resume`) but differ in 9 of 11 measured contract dimensions: output shape,
success criterion, failure shape, timeout, and refusal signal all vary per CLI.
Read the matching reference before first use on a host or after a CLI upgrade.
Never reuse one CLI's parser or refusal-keyword list for another — the
resemblance between flags is the trap, not a shortcut.

Use `coding-agent` or `codex-delegate` instead when the work is substantial
coding (feature implementation, multi-file refactors, long issue-to-PR work)
that needs a monitored background runner and a result artifact. This Skill
covers the lighter, cheaper end of the same spectrum: quick answers, research,
and single reviewable edits.

## Parse

Classify the request before choosing an engine:

- **Quick answer**: a concept or short lookup where latency matters → CodeBuddy.
- **Deep research**: repository reading or broad investigation → agy.
- **Quality-first research**: synthesis or polish where several minutes is
  acceptable → Cursor.
- **Single-file small edit**: a narrow, reviewable change → agy's apply flow
  for safety, or Cursor's implement flow for speed while watching the diff.
- **Readiness diagnosis**: determine which CLIs are actually installed and
  logged in without spending an LLM request on the probe.

Measured latency: CodeBuddy plain answers ~2-4s, CodeBuddy with tool calls
~24s, agy ~110-130s, Cursor ~235-320s.

Handle simple edits and read-only questions directly instead of delegating
when delegation would cost more turns than it saves.

## Capability detection

Follow the first available tier and stop; do not blend contracts across tiers.

1. **A quota-router-style plugin is installed** (commands such as
   `/codebuddy:research`, `/agy:research`, `/cursor:research`,
   `/agy:implement`, `/cursor:implement` resolve). Prefer it: it adds result
   persistence, `--resume` handling, and returned-ID validation that a raw
   call would otherwise have to redo. This Skill does not bundle that plugin.
2. **No plugin, the CLI binary is on `PATH`.** Invoke it directly using the
   contract in the matching reference. Parse only that CLI's own output
   shape; do not reuse another engine's parser.
3. **Neither available.** State which command or binary is missing and stop.
   Do not guess an answer or claim a delegated run occurred.

Installation check: `command -v agy`, `command -v agent` (Cursor's CLI
binary), `command -v codebuddy`. For login state, only Cursor exposes a clean
probe (`agent status`); leave agy and CodeBuddy as "unknown" rather than
guessing — do not spend a probe call to find out.
[Source: references/codebuddy.md]

## Engine contracts

- [agy](references/agy.md) — Antigravity CLI: native timeout, gives JSON on
  failure too, read and write both gated by `trustedWorkspaces`.
- [Cursor](references/cursor.md) — the `agent` CLI: no JSON on hard failure,
  `--mode ask` for read-only research, Workspace Trust gates writes.
- [CodeBuddy](references/codebuddy.md) — CodeBuddy Code: transcript-array
  output, exit code is not trustworthy, background mode (`--bg`) is broken.

## Known failure traps

Read [references/known-failure-modes.md](references/known-failure-modes.md)
before trusting any "done" or "verified" claim from these CLIs. Short version:
exit code, boolean success flags, and structured denial fields have each been
observed lying on at least one of these three CLIs. The one signal that has
not failed yet is scanning the natural-language response for refusal wording,
in both English and Chinese — check that before accepting a result.

## Resume

Use the engine-native flag and keep every read-only safety flag from the
contract when resuming:

- agy: add `--conversation <conversation_id>`.
- Cursor: add `--resume <session_id>`.
- CodeBuddy: add `--resume <session_id>`.

After every resumed call, require the returned id to exactly equal the
requested id. See
[references/known-failure-modes.md](references/known-failure-modes.md) for
why: Cursor can silently start a brand-new conversation with no error signal
at all.

## Decision rules

- Treat every CLI claim such as "verified", "completed", or "tests passed" as
  unproven until you check the filesystem, diff, or test output yourself. A
  clean exit code and a well-formed success envelope have both been observed
  alongside a guessed, unverified answer written into a file.
- Scan the final text for refusal signals in both languages, at minimum
  `blocked`, `rejected`, `denied`, `skipped`, `unable`, `被拒绝`, `禁止`,
  `跳过`, `无法`, `未能`. A hit inside the answer's own subject matter (for
  example, an answer about git behavior that says "Git 会拒绝") describes a
  third party, not the CLI refusing your request; when genuinely ambiguous,
  surface the hit and its surrounding text to the user instead of deciding
  silently.
- Never probe CodeBuddy with anything other than the exact `--version`
  command. Unknown-looking probes are sent to the model as a prompt and spend
  a real turn.
- Do not ask agy to write a user file directly; its write tool is confined to
  its own artifact directory. Ask it to return the complete replacement
  content, show that to the user, and let the calling agent write it after the
  workspace is confirmed trusted.
- For Cursor edits, default to the minimal `--trust` path rather than
  `--force` or `--yolo`, then inspect the actual diff. If the task requires
  running commands or tests, rerun them yourself — `--trust` can allow file
  edits while still denying shell execution, and Cursor cannot report from
  JSON alone whether it actually ran anything.
- Keep three separate parsers and subprocess rules. The three CLIs' flags look
  alike; measured common logic between any two of them was under ten
  substantive lines, mostly `try {}` and stdio boilerplate. Do not build a
  shared abstraction layer on top of them.

## Route

| Work | Preferred route | Why |
| --- | --- | --- |
| Quick answer or concept lookup | CodeBuddy | Fastest measured route, ~2-4s. |
| Deep research or repository reading | agy | Depth-oriented, ~110-130s. |
| Quality-first research or final polish | Cursor | Slowest, chosen when output quality matters more than latency. |
| Safe single-file edit | agy apply flow | agy proposes content; the calling agent reviews and writes it. |
| Faster single-file edit | Cursor implement | Minimal-trust path, then inspect the diff and independently rerun any requested checks. |
| Substantial or multi-file coding work | Route to `coding-agent` or `codex-delegate` instead | Out of scope here; those Skills provide a monitored runner with a result envelope. |
