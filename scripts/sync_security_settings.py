#!/usr/bin/env python3
"""Synchronize client security settings and deny rules across AI CLI tools.

Merges sensitive path deny rules and sandbox restrictions into client config files
(agy, claude, codebuddy, codex) idempotently without destroying existing user settings.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates" / "client-security"
HOME = Path.home()

CLIENT_CONFIGS = {
    "agy": {
        "path": HOME / ".gemini" / "antigravity-cli" / "settings.json",
        "template": TEMPLATES_DIR / "agy-settings.json",
        "format": "json",
    },
    "claude": {
        "path": HOME / ".claude" / "settings.json",
        "template": TEMPLATES_DIR / "claude-settings.json",
        "format": "json",
    },
    "codebuddy": {
        "path": HOME / ".codebuddy" / "settings.json",
        "template": TEMPLATES_DIR / "codebuddy-settings.json",
        "format": "json",
    },
    "codex": {
        "path": HOME / ".codex" / "config.toml",
        "template": TEMPLATES_DIR / "codex-config.toml",
        "format": "toml",
    },
}


def merge_json_security(existing: dict, template: dict) -> tuple[dict, list[str]]:
    changes: list[str] = []
    result = dict(existing)

    # 1. Workspace boundary check
    if "allowNonWorkspaceAccess" in template:
        if result.get("allowNonWorkspaceAccess") != template["allowNonWorkspaceAccess"]:
            changes.append(f"set allowNonWorkspaceAccess = {template['allowNonWorkspaceAccess']}")
            result["allowNonWorkspaceAccess"] = template["allowNonWorkspaceAccess"]

    # 2. Permissions deny list
    template_perms = template.get("permissions", {})
    template_deny = template_perms.get("deny", [])

    if template_deny:
        if "permissions" not in result:
            result["permissions"] = {}
        target_perms = result["permissions"]
        target_deny = target_perms.get("deny", [])
        if not isinstance(target_deny, list):
            target_deny = []

        existing_set = set(target_deny)
        home_str = str(HOME)
        for item in template_deny:
            rules_to_add = [item]
            if "~" in item:
                # Add absolute path variant as well to ensure CLI tools matching absolute paths are intercepted
                abs_rule = item.replace("~", home_str)
                rules_to_add.append(abs_rule)
                if abs_rule.endswith(")") and not abs_rule.endswith("/**)"):
                    # Add recursive wildcard variant
                    rules_to_add.append(abs_rule[:-1] + "/**)")

            for r in rules_to_add:
                if r not in existing_set:
                    target_deny.append(r)
                    existing_set.add(r)
                    changes.append(f"add deny rule: {r}")
        target_perms["deny"] = target_deny

    return result, changes


def merge_toml_security(existing_content: str, template_content: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    lines = existing_content.splitlines()

    # Check sandbox_mode
    has_sandbox = any(line.strip().startswith("sandbox_mode") for line in lines)
    if not has_sandbox:
        changes.append("add sandbox_mode = \"workspace-write\"")
        lines.insert(0, 'sandbox_mode = "workspace-write"')

    # Check shell_environment_policy
    if "[shell_environment_policy]" not in existing_content:
        changes.append("add [shell_environment_policy] include_only")
        lines.append("")
        lines.append("[shell_environment_policy]")
        lines.append('include_only = ["PATH", "HOME", "USER", "SHELL", "LANG", "TERM"]')

    return "\n".join(lines) + "\n", changes


def sync_client(name: str, spec: dict, dry_run: bool) -> int:
    target_path = spec["path"]
    template_path = spec["template"]

    if not template_path.is_file():
        print(f"[{name}] Warning: template not found: {template_path}")
        return 0

    print(f"=== Checking {name} ({target_path}) ===")
    changes_made = 0

    if spec["format"] == "json":
        template_data = json.loads(template_path.read_text(encoding="utf-8"))
        if target_path.is_file():
            try:
                target_data = json.loads(target_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  Error reading {target_path}: {e}")
                return 1
        else:
            target_data = {}

        merged, changes = merge_json_security(target_data, template_data)
        if not changes:
            print("  ok (all security settings and deny rules already present)")
        else:
            for ch in changes:
                prefix = "~ (dry-run)" if dry_run else "+ applied"
                print(f"  {prefix}: {ch}")
            changes_made = len(changes)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    elif spec["format"] == "toml":
        template_content = template_path.read_text(encoding="utf-8")
        target_content = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        merged_content, changes = merge_toml_security(target_content, template_content)
        if not changes:
            print("  ok (sandbox and env policy already present)")
        else:
            for ch in changes:
                prefix = "~ (dry-run)" if dry_run else "+ applied"
                print(f"  {prefix}: {ch}")
            changes_made = len(changes)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(merged_content, encoding="utf-8")

    return changes_made


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize client security settings.")
    parser.add_argument("--dry-run", action="store_true", help="Diagnose drift without modifying files.")
    parser.add_argument("client", nargs="*", help="Specific client(s) to sync (agy, claude, codebuddy, codex).")
    args = parser.parse_args()

    selected = args.client if args.client else list(CLIENT_CONFIGS.keys())
    total_changes = 0

    for name in selected:
        if name not in CLIENT_CONFIGS:
            print(f"Unknown client: {name}. Available: {', '.join(CLIENT_CONFIGS)}")
            return 1
        total_changes += sync_client(name, CLIENT_CONFIGS[name], args.dry_run)

    print()
    if args.dry_run:
        print(f"Dry run complete. {total_changes} change(s) proposed.")
    else:
        print(f"Sync complete. {total_changes} change(s) applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
