from pathlib import Path

from scripts.validate_repo import frontmatter, local_link_errors


def test_frontmatter_accepts_portable_fields(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: example-skill\ndescription: Use for examples.\n---\n\n# Example\n",
        encoding="utf-8",
    )

    fields, errors = frontmatter(skill)

    assert fields == {"name": "example-skill", "description": "Use for examples."}
    assert errors == []


def test_frontmatter_rejects_client_specific_fields(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: example-skill\ndescription: Use for examples.\nallowed-tools: Bash\n---\n",
        encoding="utf-8",
    )

    _, errors = frontmatter(skill)

    assert "unsupported frontmatter fields: allowed-tools" in errors


def test_link_check_ignores_fenced_examples_but_finds_real_links(tmp_path: Path):
    document = tmp_path / "guide.md"
    document.write_text(
        "```markdown\n![example](./missing-example.png)\n```\n\n"
        "[missing document](./missing.md)\n",
        encoding="utf-8",
    )

    assert local_link_errors(document) == ["broken local link './missing.md'"]
