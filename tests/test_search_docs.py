from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "search-docs"
CLI = SKILL / "scripts" / "search-docs"
INSTALLER = SKILL / "scripts" / "install-search-docs"
CONTRACT = SKILL / "references" / "capability-contract.json"
PROVENANCE = SKILL / "references" / "capability-provenance.json"


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, env=env)


def test_snapshot_matches_provenance_and_skill_policy() -> None:
    contract = json.loads(CONTRACT.read_text())
    provenance = json.loads(PROVENANCE.read_text())
    digest = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()

    assert digest == provenance["sha256"]
    assert contract["id"] == provenance["contract_id"]
    assert contract["version"] == provenance["contract_version"]
    assert len(provenance["upstream_commit"]) == 40
    assert provenance["license"] == "MIT"

    skill = (SKILL / "SKILL.md").read_text()
    assert "references/capability-contract.json" in skill
    assert "references/capability-provenance.json" in skill
    assert "Do not copy numeric policy" in skill
    assert "0.20" not in skill


def test_cli_reports_version_and_passes_offline_doctor() -> None:
    version = run(str(CLI), "version")
    assert version.returncode == 0, version.stderr
    assert "search-docs.v1" in version.stdout
    assert "1.0.0" in version.stdout
    assert "f9ef28280b86" in version.stdout

    doctor = run(str(CLI), "doctor", "--offline")
    assert doctor.returncode == 0, doctor.stderr
    report = json.loads(doctor.stdout)
    assert report["status"] == "ok"
    assert report["contract"]["sha256"] == report["contract"]["expected_sha256"]
    assert report["contract"]["upstream_commit"].startswith("10ef2e8fe")


def test_installer_atomically_installs_whole_skill_and_detects_drift(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skill_root = tmp_path / "skills"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    env = {**os.environ, "HOME": str(home)}
    command = (
        str(INSTALLER),
        "--target",
        "codex",
        "--skill-root",
        str(skill_root),
        "--bin-dir",
        str(bin_dir),
    )

    first = run(*command, env=env)
    assert first.returncode == 0, first.stderr
    installed = skill_root / "search-docs"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "references" / "capability-contract.json").is_file()
    assert (bin_dir / "search-docs").resolve() == installed / "scripts" / "search-docs"
    linked_version = run(str(bin_dir / "search-docs"), "version", env=env)
    assert linked_version.returncode == 0, linked_version.stderr
    assert "search-docs.v1" in linked_version.stdout

    (installed / "SKILL.md").write_text("stale\n")
    check = run(*command, "--check", env=env)
    assert check.returncode != 0
    assert "drift" in check.stderr.lower()

    second = run(*command, env=env)
    assert second.returncode == 0, second.stderr
    assert (installed / "SKILL.md").read_bytes() == (SKILL / "SKILL.md").read_bytes()
    final_check = run(*command, "--check", env=env)
    assert final_check.returncode == 0, final_check.stderr
