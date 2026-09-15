# CNB Official Docs Index

Curated pointers, not copies — CNB's own docs are the source of truth for
exact field syntax; this file only says which page to open and why. All
links verified live and consistent with this Skill's mapping table.

| Page | Read it when you need... |
|---|---|
| [Migrate from GitHub Actions](https://docs.cnb.cool/zh/build/migrate-to-cnb/migrate-from-github-actions.html) | The full official term equivalence (jobs/steps ↔ stages/jobs), plus matrix and `actions/upload-artifact` handling in more depth than this Skill's mapping table. |
| [Pipeline grammar](https://docs.cnb.cool/zh/build/grammar.html) | The authoritative field reference: every pipeline- and stage-level key (`runner`, `docker`, `git`, `services`, `env`, `imports`, `label`, `stages`, `failStages`, `endStages`, `ifNewBranch`, `ifModify`, `breakIfModify`, `retry`, `allowFailure`, `lock`, `sandbox`, `timeout`) and their accepted types. Consult this before guessing a field's shape. |
| [Trigger rules](https://docs.cnb.cool/zh/build/trigger-rule.html) | How CNB classifies trusted vs. untrusted events (PR from a fork, comment triggers, NPC events) and restricts `CNB_TOKEN` scope on untrusted ones — read before deciding which stages are safe to run on `pull_request`. |
| [Web trigger](https://docs.cnb.cool/zh/build/web-trigger.html) | The full `.cnb/web_trigger.yml` schema: `buttons[]`, all 8 `inputs[].type` values (`input`, `textarea`, `select`, `switch`, `radio`, `date`, `datetime`, `daterange`), and grouping options beyond this Skill's `select`-only examples. |
| [Crontab](https://docs.cnb.cool/zh/build/crontab.html) | Confirms the 5-minute minimum scheduling interval and the exact `"crontab: <expr>"` key syntax. |
| [Secret store](https://docs.cnb.cool/zh/repo/secret.html) | How a secrets repo file referenced via `imports` gets parsed and injected as env vars — the mechanics behind this Skill's Secrets step. |
| [Timeout strategy](https://docs.cnb.cool/zh/build/timeout.html) | Pipeline ceiling (20h) and the per-job default (2h, plus a 10-minute no-output kill) — read before migrating any long-running step (LLM batch jobs, large builds). |
| [Internal steps](https://docs.cnb.cool/zh/build/internal-steps.html) | `type: git:release` (fields: `tag`/`title`/`description`/`descriptionFromFile`/`preRelease`/`latest`/`overlying` — no `target_commitish`) and `cnbcool/attachments:latest` (uploads via `settings.attachments`, a list of paths/globs) — the two internal tasks behind this Skill's `actions/upload-artifact` and GitHub Release mapping. Worked example in [references/example.cnb.yml](example.cnb.yml). |

## A real footgun this caught

A production migration in this org had an LLM-enrichment stage killed
mid-run by the 2-hour per-job default, because the equivalent GitHub
Actions job had no such ceiling. The fix wasn't a bigger timeout (12h is
the ceiling, not a promise) — it was making the stage checkpoint its
progress and exit cleanly before the ceiling, then resume from the
checkpoint on the next run. Assume any step whose GitHub Actions
equivalent ran unbounded needs either an explicit `timeout:` or a
self-checkpoint, not just a bump to "make it longer."
