"""Tests for scripts/sync_security_settings.py.

Verifies that security deny rules and sandbox configurations are merged cleanly
without clobbering existing user settings (models, plugins, allow rules) and that
sync operations are strictly idempotent.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import sync_security_settings


def test_merge_json_security_preserves_existing_keys_and_adds_deny():
    existing = {
        "model": "gpt-5-custom",
        "allowNonWorkspaceAccess": True,
        "permissions": {
            "allow": ["command(git status)"],
            "deny": ["command(rm -rf)"],
        },
        "plugins": {"custom-plugin": True},
    }
    template = {
        "allowNonWorkspaceAccess": False,
        "permissions": {
            "deny": ["command(rm -rf)", "read_file(~/.ssh)"],
        },
    }

    merged, changes = sync_security_settings.merge_json_security(existing, template)

    assert merged["model"] == "gpt-5-custom"
    assert merged["plugins"] == {"custom-plugin": True}
    assert merged["allowNonWorkspaceAccess"] is False
    assert "command(git status)" in merged["permissions"]["allow"]
    assert "command(rm -rf)" in merged["permissions"]["deny"]
    assert "read_file(~/.ssh)" in merged["permissions"]["deny"]
    assert f"read_file({sync_security_settings.HOME}/.ssh)" in merged["permissions"]["deny"]
    assert len(changes) >= 2


def test_merge_json_security_idempotency():
    initial = {
        "allowNonWorkspaceAccess": False,
        "permissions": {
            "deny": [
                "read_file(~/.ssh)",
                f"read_file({sync_security_settings.HOME}/.ssh)",
                f"read_file({sync_security_settings.HOME}/.ssh/**)",
            ],
        },
    }
    template = {
        "allowNonWorkspaceAccess": False,
        "permissions": {
            "deny": ["read_file(~/.ssh)"],
        },
    }

    merged, changes = sync_security_settings.merge_json_security(initial, template)
    assert changes == []
    assert merged == initial


def test_merge_toml_security_adds_sandbox_and_env_policy():
    existing_toml = """[projects."/home/user/project"]
trust_level = "trusted"
"""
    template_toml = """sandbox_mode = "workspace-write"

[shell_environment_policy]
include_only = ["PATH", "HOME", "USER", "SHELL", "LANG", "TERM"]
"""

    merged, changes = sync_security_settings.merge_toml_security(existing_toml, template_toml)

    assert 'sandbox_mode = "workspace-write"' in merged
    assert '[shell_environment_policy]' in merged
    assert 'include_only = ["PATH", "HOME", "USER", "SHELL", "LANG", "TERM"]' in merged
    assert '[projects."/home/user/project"]' in merged
    assert len(changes) == 2

    # Idempotency check
    second_merged, second_changes = sync_security_settings.merge_toml_security(merged, template_toml)
    assert second_changes == []
    assert second_merged == merged


def test_sync_client_sandbox_dry_run_and_apply(tmp_path: Path):
    sandbox_home = tmp_path / "user_home"
    target_config = sandbox_home / ".gemini" / "antigravity-cli" / "settings.json"
    target_config.parent.mkdir(parents=True)
    target_config.write_text(
        json.dumps({"model": "test-model", "allowNonWorkspaceAccess": True}, indent=2),
        encoding="utf-8",
    )

    spec = {
        "path": target_config,
        "template": sync_security_settings.TEMPLATES_DIR / "agy-settings.json",
        "format": "json",
    }

    # 1. Dry run should report changes but not touch file
    changes = sync_security_settings.sync_client("agy", spec, dry_run=True)
    assert changes > 0
    data_after_dry = json.loads(target_config.read_text(encoding="utf-8"))
    assert data_after_dry["allowNonWorkspaceAccess"] is True  # untouched

    # 2. Actual run should apply changes
    applied_changes = sync_security_settings.sync_client("agy", spec, dry_run=False)
    assert applied_changes == changes
    data_after_apply = json.loads(target_config.read_text(encoding="utf-8"))
    assert data_after_apply["allowNonWorkspaceAccess"] is False
    assert data_after_apply["model"] == "test-model"  # preserved!
    assert "read_file(~/.ssh)" in data_after_apply["permissions"]["deny"]

    # 3. Running again should report 0 changes (idempotent)
    recheck_changes = sync_security_settings.sync_client("agy", spec, dry_run=False)
    assert recheck_changes == 0
