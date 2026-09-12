"""Regression tests for scripts/mcp_tool.py.

The scenarios mirror the defects found when this tool was first reviewed:
a config that fails to parse must never be rewritten, secrets must come from
the environment rather than the catalog, and process termination must match
the server's own command line instead of its bare catalog name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import mcp_tool

REPO_ROOT = Path(__file__).resolve().parents[1]

CATALOG = {
    "schema_version": 1,
    "servers": {
        "plain": {
            "command": "npx",
            "args": ["-y", "plain-mcp"],
            "category": "test",
            "description": "no environment references",
        },
        "secret-server": {
            "type": "http",
            "url": "https://example.invalid/doc?apikey=${TEST_TOKEN}",
            "category": "test",
        },
        "defaulted": {
            "command": "uvx",
            "args": ["mcp", "--db", "${DB_PATH:-./data.db}"],
            "category": "test",
        },
    },
}


class Sandbox:
    """A fake HOME with two live clients and one absent client."""

    def __init__(self, home: Path):
        self.home = home
        self.claude = home / ".claude.json"
        self.codebuddy = home / ".codebuddy" / "mcp.json"
        self.gemini = home / ".gemini" / "config" / "mcp_config.json"

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    home = tmp_path / "client-home-dir"
    (home / ".codebuddy").mkdir(parents=True)
    (home / ".claude.json").write_text(
        '{"numStartups": 42, "theme": "dark"}\n', encoding="utf-8"
    )
    (home / ".codebuddy" / "mcp.json").write_text(
        '{"mcpServers": {"existing": {"command": "echo"}}}\n', encoding="utf-8"
    )

    box = Sandbox(home)
    monkeypatch.setattr(
        mcp_tool,
        "GLOBAL_TARGETS",
        [
            ("claude-code", box.claude),
            ("codebuddy", box.codebuddy),
            ("gemini", box.gemini),
        ],
    )
    # Neutralise the discovered IDE target so tests see exactly three clients.
    monkeypatch.setattr(mcp_tool, "CODEBUDDY_IDE_CACHE", tmp_path / "no-such-cache")
    monkeypatch.delenv("CODEBUDDY_IDE_MCP_SETTINGS", raising=False)

    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG, indent=2), encoding="utf-8")
    monkeypatch.setattr(mcp_tool, "CATALOG_FILE", catalog)

    for variable in ("TEST_TOKEN", "DB_PATH"):
        monkeypatch.delenv(variable, raising=False)
    return box


def run(subcommand: str, **overrides) -> int:
    """Invoke a subcommand the way main() does, ToolError meaning exit code 1."""
    args = SimpleNamespace(
        subcommand=subcommand, name=None, dir=".", dry_run=False, create=False, kill=False
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    try:
        return mcp_tool.COMMANDS[subcommand](args)
    except mcp_tool.ToolError:
        return 1


def test_enable_preserves_unrelated_settings_and_existing_servers(sandbox):
    assert run("enable", name="plain") == 0

    claude = sandbox.read(sandbox.claude)
    assert claude["numStartups"] == 42
    assert claude["theme"] == "dark"
    assert "plain" in claude["mcpServers"]

    codebuddy = sandbox.read(sandbox.codebuddy)
    assert "existing" in codebuddy["mcpServers"]
    assert "plain" in codebuddy["mcpServers"]


def test_enable_backs_up_global_config_and_keeps_first_backup(sandbox):
    original = sandbox.claude.read_text(encoding="utf-8")
    assert run("enable", name="plain") == 0
    assert sandbox.claude.with_name(".claude.json.bak").read_text(encoding="utf-8") == original

    # A second enable is a no-op, so the backup must not be degraded.
    assert run("enable", name="plain") == 0
    assert sandbox.claude.with_name(".claude.json.bak").read_text(encoding="utf-8") == original


def test_enable_skips_missing_clients_without_create(sandbox):
    assert run("enable", name="plain") == 0
    assert not sandbox.gemini.exists()


def test_create_flag_writes_missing_clients(sandbox):
    assert run("enable", name="plain", create=True) == 0
    assert "plain" in sandbox.read(sandbox.gemini)["mcpServers"]


def test_unparseable_config_is_reported_and_left_untouched(sandbox):
    broken = '{\n  "numStartups": 42,\n}\n'  # trailing comma: invalid JSON
    sandbox.claude.write_text(broken, encoding="utf-8")

    assert run("enable", name="plain") == 1
    assert sandbox.claude.read_text(encoding="utf-8") == broken
    assert not sandbox.claude.with_name(".claude.json.bak").exists()


def test_unset_secret_fails_instead_of_writing_a_literal(sandbox, monkeypatch):
    monkeypatch.delenv("TEST_TOKEN", raising=False)

    assert run("enable", name="secret-server") == 1
    written = json.dumps(sandbox.read(sandbox.codebuddy))
    assert "example.invalid" not in written
    assert "${TEST_TOKEN}" not in written


def test_secret_resolved_from_environment(sandbox, monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "s3cr3t")

    assert run("enable", name="secret-server") == 0
    url = sandbox.read(sandbox.codebuddy)["mcpServers"]["secret-server"]["url"]
    assert url == "https://example.invalid/doc?apikey=s3cr3t"


def test_default_value_and_environment_override(sandbox, monkeypatch):
    assert run("enable", name="defaulted") == 0
    args = sandbox.read(sandbox.codebuddy)["mcpServers"]["defaulted"]["args"]
    assert args == ["mcp", "--db", "./data.db"]

    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    assert run("enable", name="defaulted") == 0
    args = sandbox.read(sandbox.codebuddy)["mcpServers"]["defaulted"]["args"]
    assert args == ["mcp", "--db", "/tmp/custom.db"]


def test_dry_run_changes_nothing(sandbox):
    before = sandbox.codebuddy.read_text(encoding="utf-8")
    assert run("enable", name="plain", dry_run=True) == 0
    assert sandbox.codebuddy.read_text(encoding="utf-8") == before
    assert not sandbox.codebuddy.with_name("mcp.json.bak").exists()
    assert not sandbox.gemini.exists()


def test_disable_removes_server_and_drops_empty_block(sandbox):
    run("enable", name="plain")
    assert run("disable", name="plain") == 0

    # codebuddy still holds an unrelated server, so its MCP block stays.
    codebuddy = sandbox.read(sandbox.codebuddy)
    assert codebuddy == {"mcpServers": {"existing": {"command": "echo"}}}

    # claude.json had no other server, so the emptied block is dropped
    # while its unrelated settings survive.
    claude = sandbox.read(sandbox.claude)
    assert claude == {"numStartups": 42, "theme": "dark"}


def test_attach_and_detach_project_file_without_backup(sandbox, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    mcp_file = project / ".mcp.json"

    assert run("attach", name="plain", dir=str(project)) == 0
    assert "plain" in sandbox.read(mcp_file)["mcpServers"]
    assert not mcp_file.with_name(".mcp.json.bak").exists()

    assert run("detach", name="plain", dir=str(project)) == 0
    assert json.loads(mcp_file.read_text(encoding="utf-8")) == {}


def test_list_labels_clients_by_name_not_by_directory(sandbox, capsys):
    run("enable", name="plain")
    capsys.readouterr()  # discard the enable output; only list's output matters

    assert run("list") == 0
    output = capsys.readouterr().out
    assert "[active in: claude-code, codebuddy]" in output
    assert sandbox.home.name not in output  # the home directory is not a client


def test_stop_processes_matches_only_the_servers_own_command_line(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[:2] == ["pgrep", "-f"]:
            return SimpleNamespace(stdout="111\n222\n", stderr="")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(mcp_tool.subprocess, "run", fake_run)

    definition = {"command": "uvx", "args": ["mcp-figma", "--token", "x"]}
    mcp_tool.stop_processes(definition, "figma", dry_run=True)
    assert calls == [["pgrep", "-f", "uvx.*mcp\\-figma"]]
    assert "would stop" in capsys.readouterr().out

    mcp_tool.stop_processes(definition, "figma", dry_run=False)
    assert calls[-1] == ["kill", "111", "222"]
    assert "stopped 2" in capsys.readouterr().out


def test_real_catalog_never_embeds_credentials():
    """The catalog lives in a public repository; credentials must be ${VAR} refs."""
    catalog = json.loads((REPO_ROOT / "mcp" / "catalog.json").read_text(encoding="utf-8"))
    pattern = re.compile(r"[?&](?:apikey|token|key|secret)=([^&\s]+)", re.IGNORECASE)

    for server, info in catalog["servers"].items():
        for value in re.findall(r'"([^"]*)"', json.dumps(info)):
            for match in pattern.finditer(value):
                assert match.group(1).startswith("${"), (
                    f"server '{server}' embeds a literal credential; "
                    f"use an environment variable reference instead"
                )
