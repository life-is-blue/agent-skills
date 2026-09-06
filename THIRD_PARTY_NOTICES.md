# Third-party notices

## OpenClaw coding-agent

`skills/openclaw-coding-agent/references/upstream-SKILL.md` is an unmodified
snapshot of OpenClaw's bundled `coding-agent` Skill. OpenClaw is licensed under
the MIT License, Copyright (c) 2026 OpenClaw Foundation. The applicable license
text is preserved at
`skills/openclaw-coding-agent/references/LICENSE.openclaw`.

The adapted `openclaw-coding-agent` and portable `coding-agent` implementations
are maintained by this repository and are not presented as upstream OpenClaw
files.

## git-library capability contract

`skills/search-docs/references/capability-contract.json` is an unmodified
snapshot exported from git-library. Its repository, source path, exact commit,
SHA-256 digest, and upstream MIT license declaration are retained in
`skills/search-docs/references/capability-provenance.json`.

## leader (merged into coordinator)

`skills/coordinator/references/brief-authoring.md`, `brief-anatomy.md`, and
`brief-style.md` are adapted from the `leader` skill in
[KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)
(upstream LICENSE included in that repository). Local changes: frontmatter
removed, cross-skill handoff sections rewritten as tier pointers inside the
`coordinator` skill.

## grill-with-docs (merged into coordinator)

`skills/coordinator/references/grilling.md`, `adr-format.md`, and
`context-format.md` are adapted from the `grill-with-docs`, `grilling`, and
`domain-modeling` skills in
[mattpocock/skills](https://github.com/mattpocock/skills), licensed under the
MIT License, Copyright (c) 2026 Matt Pocock. Upstream ships the interview and
the documentation method as three interdependent skills; this repository
merges them into the `coordinator` skill's Tier 1 module and drops the
`disable-model-invocation` frontmatter field, which this repository's skill
contract does not support.
