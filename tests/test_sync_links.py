"""Regression tests for scripts/sync_links.sh.

The scenarios mirror the defects found when this script was first reviewed:
`ln -sfn` against an existing real directory silently nests a link inside it,
the default command was the most destructive one, and stale links were never
pruned. Each test drives the real script with HOME (client side) and
AGENT_SKILLS_SIBLINGS (source side) both pointed at a sandbox, so no test
depends on sibling repos actually being checked out next to this one.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync_links.sh"

CLIENT_DIRS = [
    ".agents/skills",
    ".codex/skills",
    ".tcodex/skills",
    ".codebuddy/skills",
    ".claude/skills",
    ".tclaude/skills",
    ".gemini/antigravity-cli/skills",
]

# In-repo scoped skills: source always exists once this repo is checked out.
IN_REPO_SKILLS = {
    "coding-agent": REPO_ROOT / "skills" / "coding-agent",
    "coordinator": REPO_ROOT / "skills" / "coordinator",
    "github-actions-to-cnb": REPO_ROOT / "skills" / "github-actions-to-cnb",
    "gongfeng": REPO_ROOT / "skills" / "gongfeng",
    "search-docs": REPO_ROOT / "skills" / "search-docs",
}

# Sibling-repo scoped skills, as "name": ("sibling repo", "skill name"). The
# real sources only exist on a machine that happens to have those repos
# checked out next to this one; tests fabricate stand-ins instead.
SIBLING_SKILLS = {
    "cnb-api": ("cnb-skill", "cnb-api"),
    "cnb-pipeline": ("cnb-skill", "cnb-pipeline"),
    "wecom-unified": ("wecom-unified", "wecom-unified"),
}

CHANGE_LINE = re.compile(r"^  [+~-] ", re.MULTILINE)


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / "sync-home"
    for relative in CLIENT_DIRS:
        (home / relative).mkdir(parents=True)
    return home


def make_siblings(tmp_path: Path) -> Path:
    """Fabricate stand-in sibling checkouts under tmp_path and return their root."""
    root = tmp_path / "siblings"
    for name, (repo, skill) in SIBLING_SKILLS.items():
        skill_dir = root / repo / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"{name}\n", encoding="utf-8")
    return root


def scoped_for(siblings: Path) -> dict[str, Path]:
    scoped = dict(IN_REPO_SKILLS)
    for name, (repo, skill) in SIBLING_SKILLS.items():
        scoped[name] = siblings / repo / "skills" / skill
    return scoped


def run_script(
    home: Path, *arguments: str, siblings: Path | None = None
) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home)}
    if siblings is not None:
        env["AGENT_SKILLS_SIBLINGS"] = str(siblings)
    return subprocess.run(
        ["bash", str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        env=env,
    )


def count_changes(output: str) -> int:
    return len(CHANGE_LINE.findall(output))


def test_sync_links_every_scoped_skill_into_every_client(tmp_path: Path):
    home = make_home(tmp_path)
    siblings = make_siblings(tmp_path)
    scoped = scoped_for(siblings)

    result = run_script(home, "sync", siblings=siblings)

    assert result.returncode == 0, result.stderr
    for relative in CLIENT_DIRS:
        client = home / relative
        for name, source in scoped.items():
            link = client / name
            assert link.is_symlink(), f"{client}/{name} is not a symlink"
            assert link.resolve() == source.resolve()


def test_sync_refuses_to_nest_a_link_inside_a_real_directory(tmp_path: Path):
    home = make_home(tmp_path)
    siblings = make_siblings(tmp_path)
    scoped = scoped_for(siblings)
    shadowed = home / ".codebuddy" / "skills" / "search-docs"
    shadowed.mkdir()
    (shadowed / "SKILL.md").write_text("shadow\n", encoding="utf-8")

    result = run_script(home, "sync", siblings=siblings)

    assert result.returncode == 1
    assert "REFUSED" in result.stderr
    # The real directory is intact and no link was nested inside it.
    assert (shadowed / "SKILL.md").read_text(encoding="utf-8") == "shadow\n"
    assert list(shadowed.iterdir()) == [shadowed / "SKILL.md"]
    # Every other scoped skill in the same client was still linked.
    for name in scoped:
        if name != "search-docs":
            assert (shadowed.parent / name).is_symlink()


def test_sync_prunes_stale_owned_links_but_keeps_foreign_ones(tmp_path: Path):
    home = make_home(tmp_path)
    siblings = make_siblings(tmp_path)
    client = home / ".claude" / "skills"
    # A link into the repository's skills tree that is no longer scoped.
    (client / "branded-pptx").symlink_to(REPO_ROOT / "skills" / "branded-pptx")
    # A link this script does not own (a hub install, say).
    foreign_source = tmp_path / "custom-hub-skill-real"
    foreign_source.mkdir()
    (client / "custom-hub-skill").symlink_to(foreign_source)

    result = run_script(home, "sync", siblings=siblings)

    assert result.returncode == 0, result.stderr
    assert not (client / "branded-pptx").exists()
    assert (client / "custom-hub-skill").resolve() == foreign_source


def test_check_reports_drift_until_sync_has_run(tmp_path: Path):
    home = make_home(tmp_path)
    siblings = make_siblings(tmp_path)

    assert run_script(home, "status", siblings=siblings).returncode == 0
    assert run_script(home, "check", siblings=siblings).returncode == 1

    assert run_script(home, "sync", siblings=siblings).returncode == 0
    assert run_script(home, "check", siblings=siblings).returncode == 0


def test_bare_invocation_is_read_only(tmp_path: Path):
    home = make_home(tmp_path)

    result = run_script(home)

    assert result.returncode == 0
    assert result.stdout.startswith("=== Scoped links")
    for relative in CLIENT_DIRS:
        assert list((home / relative).iterdir()) == []


def test_sync_is_idempotent_and_dry_run_writes_nothing(tmp_path: Path):
    home = make_home(tmp_path)
    siblings = make_siblings(tmp_path)
    scoped = scoped_for(siblings)

    dry = run_script(home, "sync", "--dry-run", siblings=siblings)
    assert dry.returncode == 0
    assert count_changes(dry.stdout) == len(scoped) * len(CLIENT_DIRS)
    for relative in CLIENT_DIRS:
        assert list((home / relative).iterdir()) == []

    assert run_script(home, "sync", siblings=siblings).returncode == 0
    second = run_script(home, "sync", siblings=siblings)
    assert second.returncode == 0
    assert count_changes(second.stdout) == 0, "second sync should change nothing"
