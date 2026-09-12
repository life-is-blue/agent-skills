from pathlib import Path

from scripts import validate_repo
from scripts.validate_repo import frontmatter, local_link_errors, syntax_errors


def test_repo_scripts_pass_the_syntax_gate():
    """The gate covers repo-root scripts/ too, not only skills/."""
    assert syntax_errors() == []


def test_syntax_gate_flags_broken_scripts(tmp_path: Path, monkeypatch):
    broken = tmp_path / "oops.sh"
    broken.write_text("if [ then\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "REPO_SCRIPTS_DIR", tmp_path)

    failures = {path.name for path, _ in syntax_errors()}

    assert "oops.sh" in failures


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
