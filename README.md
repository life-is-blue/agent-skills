# open-agent-skills-pack

A standalone, open-source skill pack extracted from local production repositories.

## Included Skills

- `search-docs`
  - Source: `git-library/.claude/skills/search-docs/`
  - Purpose: Query docs from MCP knowledge libraries.

- `wechat-format`
  - Source: `formatter/.agents/skills/wechat-format/`
  - Purpose: Format Markdown to WeChat-ready HTML via API.

- `pdf-to-markdown`
  - Source: `one-key-claude/.gemini/skills/pdf-to-markdown/`
  - Purpose: Convert PDF text to Markdown with heuristic layout reconstruction.

## Layout

- `skills/<skill-name>/SKILL.md`
- Optional scripts are included under each skill folder.

## Notes

These skills are copied as-is from source projects to keep extraction minimal and non-invasive.
