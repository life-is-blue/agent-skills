---
name: codex-delegate
description: Delegate a coding, debugging, or review task to the Codex CLI and receive a machine-readable result envelope with thread id, touched files, executed commands, and token usage. Use when another agent must call Codex programmatically, run it in the background, resume a previous Codex thread, or gate on its structured output; do not use for simple edits, read-only lookup, or when a different provider is required.
---

# Codex Delegate

Run `scripts/codex_run.py` to execute the Codex CLI as a monitored job. Every
command prints a stable JSON envelope with `--json`, so a calling agent can act
on the result instead of scraping console text.

Use [references/result-contract.md](references/result-contract.md) for the
envelope fields and exit codes, and
[references/codex-cli.md](references/codex-cli.md) for the verified CLI
behavior this adapter depends on.

## Route

- Use this Skill for Codex-specific work that needs a structured result,
  background execution, thread resume, or the built-in reviewer.
- Use `coding-agent` when the provider may be Claude Code, TClaude, CodeBuddy,
  or OpenCode, or when a plain streamed log is enough.
- Handle simple edits and read-only questions directly.

## Preflight

```bash
SKILL_DIR=/path/to/codex-delegate

python3 "$SKILL_DIR/scripts/codex_run.py" doctor
```

`doctor` reports the resolved `codex` binary, its version, and login state. Stop
and report to the user when it is not ready; do not improvise an auth flow.

Codex requires a Git repository. For a modifying task:

1. Confirm the target repository, canonical remote, target base, and trust of
   the source ref.
2. Fetch the base and create an isolated worktree. Never let a background worker
   edit the primary checkout.
3. Record the start SHA and include it in the prompt.

For scratch work, create a temporary directory and run `git init` first. The
adapter never passes `--skip-git-repo-check`; it fails fast with `E_INPUT`
instead.

## Write the prompt

Put the complete task in a file. State the intended outcome, scope boundaries,
the worktree and starting SHA, files that must not change, required tests, and
whether commit, push, or PR is authorized. Do not put secrets in the prompt.

[references/prompting.md](references/prompting.md) has the block structure that
works best with Codex.

## Run

Read-only investigation, foreground:

```bash
python3 "$SKILL_DIR/scripts/codex_run.py" start \
  --workdir /path/to/worktree \
  --prompt-file /path/to/prompt.txt \
  --json
```

Write-capable work in an isolated worktree, in the background:

```bash
python3 "$SKILL_DIR/scripts/codex_run.py" start \
  --workdir /path/to/worktree \
  --prompt-file /path/to/prompt.txt \
  --write --background --timeout 3600 --json
```

`--background` returns immediately with the job id. Then poll or block:

```bash
python3 "$SKILL_DIR/scripts/codex_run.py" status <job-id> --json
python3 "$SKILL_DIR/scripts/codex_run.py" wait <job-id> --timeout 900 --json
python3 "$SKILL_DIR/scripts/codex_run.py" result <job-id> --json
python3 "$SKILL_DIR/scripts/codex_run.py" logs <job-id>
python3 "$SKILL_DIR/scripts/codex_run.py" cancel <job-id>
```

Continue the newest recorded thread for the same worktree, or an explicit one:

```bash
python3 "$SKILL_DIR/scripts/codex_run.py" start --workdir /path/to/worktree \
  --prompt-file /path/to/followup.txt --resume-last --write --json
```

Send only the delta instruction on a resume. Sandbox mode is not inherited, so
pass `--write` again when the follow-up must edit files.

Built-in reviewer, always read-only:

```bash
python3 "$SKILL_DIR/scripts/codex_run.py" review --workdir /path/to/repo --uncommitted --json
python3 "$SKILL_DIR/scripts/codex_run.py" review --workdir /path/to/repo --base main --background
```

Add `--model`, `--effort`, and `--output-schema FILE` only when the task needs
them. With no model or effort, Codex uses its own configured defaults.

## Consume the result

Read `status` and `exit_code` first, then `final_message`, `touched_files`, and
`commands`. Preserve Codex's own verdict, severities, file paths, and line
numbers when reporting to the user. Never turn a failed Codex run into your own
implementation attempt; report the failure and stop.

After a review, present the findings and stop. Ask the user which findings to
fix before editing anything.

## Safety

- The default sandbox is `read-only`.
- `--write` maps to `-s workspace-write -a never`.
- `--unsafe` maps to `--dangerously-bypass-approvals-and-sandbox`. Pass it only
  with explicit user authorization in a trusted, externally sandboxed worktree.
- Session state lives under `--state-dir`, `CODEX_DELEGATE_STATE_DIR`,
  `$XDG_STATE_HOME/codex-delegate`, or `~/.local/state/codex-delegate`. It holds
  the prompt, the raw event stream, and Codex stderr; treat it as sensitive.

## Verify

1. Check the envelope `status`, `exit_code`, and `errors`.
2. Review the diff in the worktree. A zero exit code alone proves nothing.
3. Confirm the commands Codex reported actually cover the required tests, and
   rerun the repository's checks from the parent agent.
4. Refresh the target base and verify ancestry before pushing a new branch.
5. Never force-push or rewrite a shared branch without explicit authorization.
