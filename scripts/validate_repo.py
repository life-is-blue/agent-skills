#!/usr/bin/env python3
"""Validate the portable Skill contract and repository-local references."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
CATALOG = SKILLS_DIR / "catalog.json"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
RESOURCE_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:scripts|references|assets|templates)/[A-Za-z0-9_./-]+)"
)
ALLOWED_DISTRIBUTIONS = {"bundled", "adapter", "protocol-only"}


def frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}, ["SKILL.md must start with YAML frontmatter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["SKILL.md frontmatter is not closed"]

    fields: dict[str, str] = {}
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.startswith((" ", "\t")):
            errors.append(f"line {number}: nested or blank frontmatter is not allowed")
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            errors.append(f"line {number}: invalid frontmatter field")
            continue
        key, value = match.groups()
        if key in fields:
            errors.append(f"line {number}: duplicate frontmatter field {key!r}")
        fields[key] = value.strip().strip('"\'')

    expected = {"name", "description"}
    missing = expected - fields.keys()
    extra = fields.keys() - expected
    if missing:
        errors.append(f"missing frontmatter fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unsupported frontmatter fields: {', '.join(sorted(extra))}")
    for key in expected & fields.keys():
        if not fields[key]:
            errors.append(f"frontmatter field {key!r} must not be empty")
    return fields, errors


def local_link_errors(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^(```|~~~).*?^\1\s*$", "", text, flags=re.MULTILINE | re.DOTALL)
    for raw_target in LINK_RE.findall(text):
        target = raw_target.strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        if not (path.parent / target).resolve().exists():
            errors.append(f"broken local link {raw_target!r}")
    return errors


def resource_errors(skill_dir: Path, distribution: str) -> list[str]:
    if distribution == "protocol-only":
        return []
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    errors: list[str] = []
    for target in sorted(set(RESOURCE_RE.findall(text))):
        clean = target.rstrip(".,;:)")
        if not (skill_dir / clean).exists():
            errors.append(f"referenced resource does not exist: {clean}")
    return errors


def syntax_errors() -> list[tuple[Path, str]]:
    errors: list[tuple[Path, str]] = []
    for path in sorted(SKILLS_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".py":
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except (SyntaxError, UnicodeError) as exc:
                errors.append((path, f"Python syntax error: {exc}"))
        elif path.suffix == ".sh" or (
            path.parent.name == "scripts"
            and path.read_bytes()[:32].startswith((b"#!/bin/bash", b"#!/usr/bin/env bash"))
        ):
            result = subprocess.run(
                ["bash", "-n", str(path)], capture_output=True, text=True, check=False
            )
            if result.returncode:
                errors.append((path, result.stderr.strip() or "shell syntax error"))
    return errors


def main() -> int:
    failures: list[tuple[Path, str]] = []
    warnings: list[tuple[Path, str]] = []

    try:
        catalog_data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR {CATALOG.relative_to(ROOT)}: {exc}")
        return 1

    if catalog_data.get("schema_version") != 1:
        failures.append((CATALOG, "schema_version must be 1"))
    entries = catalog_data.get("skills")
    if not isinstance(entries, list):
        failures.append((CATALOG, "skills must be a list"))
        entries = []

    catalog: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"name", "distribution"}:
            failures.append((CATALOG, f"skills[{index}] must contain only name and distribution"))
            continue
        name, distribution = entry["name"], entry["distribution"]
        if name in catalog:
            failures.append((CATALOG, f"duplicate skill entry: {name}"))
        if distribution not in ALLOWED_DISTRIBUTIONS:
            failures.append((CATALOG, f"invalid distribution for {name}: {distribution}"))
        catalog[name] = distribution

    all_skill_dirs = sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())
    for path in all_skill_dirs:
        if not (path / "SKILL.md").is_file():
            failures.append((path, "Skill directory is missing SKILL.md"))
    skill_dirs = [path for path in all_skill_dirs if (path / "SKILL.md").is_file()]
    directory_names = {path.name for path in skill_dirs}
    if directory_names != set(catalog):
        missing = directory_names - set(catalog)
        stale = set(catalog) - directory_names
        if missing:
            failures.append((CATALOG, f"missing catalog entries: {', '.join(sorted(missing))}"))
        if stale:
            failures.append((CATALOG, f"catalog entries without Skill directories: {', '.join(sorted(stale))}"))

    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not NAME_RE.fullmatch(skill_dir.name):
            failures.append((skill_dir, "directory name must use lowercase hyphen-case"))
        fields, errors = frontmatter(skill_file)
        failures.extend((skill_file, error) for error in errors)
        if fields.get("name") != skill_dir.name:
            failures.append((skill_file, "frontmatter name must match its directory"))
        failures.extend((skill_file, error) for error in local_link_errors(skill_file))
        if skill_dir.name in catalog:
            distribution = catalog[skill_dir.name]
            failures.extend(
                (skill_file, error)
                for error in resource_errors(skill_dir, distribution)
            )
            implementation_dirs = {
                name
                for name in ("scripts", "assets", "templates")
                if (skill_dir / name).is_dir()
            }
            if distribution == "bundled" and not implementation_dirs:
                failures.append((skill_file, "bundled Skill must ship scripts, assets, or templates"))
            if distribution == "adapter" and "scripts" not in implementation_dirs:
                failures.append((skill_file, "adapter Skill must ship a scripts directory"))
            if distribution == "protocol-only" and implementation_dirs:
                failures.append(
                    (
                        skill_file,
                        "protocol-only Skill must not ship implementation directories: "
                        + ", ".join(sorted(implementation_dirs)),
                    )
                )
        line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            warnings.append((skill_file, f"{line_count} lines; consider progressive disclosure"))

    skill_files = {skill_dir / "SKILL.md" for skill_dir in skill_dirs}
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" not in path.parts and path not in skill_files:
            failures.extend((path, error) for error in local_link_errors(path))
    failures.extend(syntax_errors())

    for path, message in warnings:
        print(f"WARN  {path.relative_to(ROOT)}: {message}")
    for path, message in failures:
        print(f"ERROR {path.relative_to(ROOT)}: {message}")
    if failures:
        print(f"Validation failed with {len(failures)} error(s).")
        return 1
    print(f"Validated {len(skill_dirs)} skills with {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
