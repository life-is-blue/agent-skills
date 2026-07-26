# Prompting Codex

Codex follows an operator brief better than a conversation. Keep the prompt
compact and block-structured, and state what "done" looks like instead of
assuming Codex will infer it.

The block approach below is adapted from the prompting guidance in OpenAI's
Codex plugin for Claude Code (<https://github.com/openai/codex-plugin-cc>,
Apache-2.0). No upstream text is reproduced here.

## Baseline blocks

```xml
<task>
Fix the failing integration test in tests/test_sync.py::test_retry_backoff.
Worktree /tmp/wt-sync at 4f21c9a, branch fix/sync-backoff.
</task>

<constraints>
Do not change the public signature of SyncClient.
Do not touch tests/fixtures/.
</constraints>

<verification_loop>
Run `pytest tests/test_sync.py -q` and iterate until it passes.
Report the final command and its exit code.
</verification_loop>

<output_contract>
Finish with: what changed, why, files touched, verification result.
Keep it under 15 lines.
</output_contract>
```

## Add blocks only when the task needs them

| Task type | Add |
|---|---|
| Implementation, debugging | `verification_loop`, `completeness_contract` |
| Write-capable runs | `action_safety`: stay inside the named scope, no unrelated refactors |
| Review, adversarial review | `grounding_rules`: cite file and line, mark inference as inference |
| Research, recommendation | `citation_rules`, and require open questions to be listed |
| Anything with unknowns | `missing_context_gating`: what to assume vs. when to stop and ask |

## Rules that matter in practice

- One task per run. Split unrelated asks into separate jobs.
- Name the worktree and starting SHA. Codex cannot guess which checkout is safe.
- Say explicitly whether commit, push, or PR creation is authorized. The default
  should be no external writes.
- State the exact verification command instead of "make sure it works".
- Tighten the prompt before raising `--effort`. Reasoning effort rarely fixes a
  vague contract.
- On `--resume-last`, send only the delta instruction. Restate the whole task
  only when the direction changed materially.
- Never include secrets, tokens, or internal auth steps. The prompt is written
  to the job directory in plain text.

## Structured output

When the caller needs to branch on the result, pass `--output-schema FILE` with
a JSON Schema and ask for that exact shape in the prompt. The adapter parses the
final message into `structured_output`; a parse failure leaves it `null` and the
raw text stays in `final_message`.
