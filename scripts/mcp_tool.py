#!/usr/bin/env python3
"""
mcp_tool.py - Single Source of Truth (SSOT) manager for Model Context Protocol
(MCP) servers.

Manage MCP servers across local AI clients (Claude Code, CodeBuddy,
Gemini/Antigravity) or attach them locally to a project-level .mcp.json.

Client configuration files hold far more than their MCP block. This tool
therefore never rewrites a file it could not parse, writes atomically, and keeps
a .bak copy of every global client config it replaces.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = REPO_ROOT / "mcp" / "catalog.json"

# client name -> config path. Names are carried explicitly because a path is a
# poor label: the parent of ~/.claude.json is the home directory, not a client.
GLOBAL_TARGETS: list[tuple[str, Path]] = [
    ("claude-code", Path.home() / ".claude.json"),
    ("codebuddy", Path.home() / ".codebuddy" / "mcp.json"),
    ("gemini", Path.home() / ".gemini" / "config" / "mcp_config.json"),
]

# The CodeBuddy IDE keeps its config under an app-managed cache whose layout
# changes between releases, so it is discovered rather than hardcoded, and it is
# never created: that directory belongs to the application.
CODEBUDDY_IDE_CACHE = (
    Path.home() / "Library" / "Application Support" / "CodeBuddyExtension" / "Cache"
)

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ToolError(Exception):
    """A user-facing failure: bad catalog, unparseable config, unset variable."""


def codebuddy_ide_target() -> tuple[str, Path] | None:
    override = os.environ.get("CODEBUDDY_IDE_MCP_SETTINGS")
    if override:
        return ("codebuddy-ide", Path(override).expanduser())
    matches = sorted(CODEBUDDY_IDE_CACHE.glob("*/mcp/settings.json"))
    if matches:
        return ("codebuddy-ide", matches[0])
    return None


def global_targets() -> list[tuple[str, Path]]:
    targets = list(GLOBAL_TARGETS)
    ide = codebuddy_ide_target()
    if ide is not None:
        targets.append(ide)
    return targets


def load_catalog() -> dict:
    if not CATALOG_FILE.exists():
        raise ToolError(f"catalog not found: {CATALOG_FILE}")
    try:
        data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError(f"catalog is not valid JSON ({exc})") from exc
    servers = data.get("servers")
    if not isinstance(servers, dict):
        raise ToolError("catalog must contain a 'servers' object")
    return servers


def read_config(path: Path) -> dict:
    """Parse a client config.

    A missing file is an empty config. An unparseable one is an error: returning
    {} here would let the next write replace the whole file with just the MCP
    block, destroying every other setting it holds.
    """
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolError(f"{path} is not valid JSON ({exc}); refusing to touch it") from exc
    if not isinstance(data, dict):
        raise ToolError(f"{path} is not a JSON object; refusing to touch it")
    return data


def write_config(path: Path, data: dict, *, backup: bool, dry_run: bool) -> None:
    """Write atomically, optionally keeping a .bak of the previous contents.

    Global client configs are backed up because a mistake there is not
    version-controlled and holds unrelated settings. Project .mcp.json files are
    not: a stray .mcp.json.bak in a user's repository is noise, and git already
    holds the previous revision.
    """
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    handle, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def resolve_env(value: str, server: str) -> str:
    """Resolve ${VAR} and ${VAR:-default} references, failing loudly when unset.

    Substituting the literal `${VAR}` would silently write a broken endpoint, so
    a reference with no default and no value is an error.
    """

    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        if name in os.environ:
            return os.environ[name]
        if default is not None:
            return default
        raise ToolError(
            f"server '{server}' references ${{{name}}}, which is not set; "
            f"export it before running this command"
        )

    return ENV_REF.sub(replace, value)


def resolve_tree(value, server: str):
    if isinstance(value, str):
        return resolve_env(value, server)
    if isinstance(value, list):
        return [resolve_tree(item, server) for item in value]
    if isinstance(value, dict):
        return {key: resolve_tree(item, server) for key, item in value.items()}
    return value


def server_definition(raw: dict, server: str) -> dict:
    """Drop catalog-only metadata and resolve ${VAR} references."""
    definition = {key: item for key, item in raw.items() if key not in ("category", "description")}
    return resolve_tree(definition, server)


def stop_processes(definition: dict, server: str, dry_run: bool) -> None:
    """Terminate processes started from this server's own command line.

    Matching the bare catalog name (as `pkill -f figma` would) also kills
    unrelated programs that merely mention it, so the pattern is built from the
    server's command and its first argument.
    """
    parts = [str(definition.get("command", ""))]
    parts += [str(arg) for arg in definition.get("args", [])[:1]]
    parts = [part for part in parts if part]
    if not parts:
        print(f"  -> nothing to match for '{server}'; not stopping any process")
        return
    pattern = ".*".join(re.escape(part) for part in parts)
    found = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    pids = found.stdout.split()
    if not pids:
        print(f"  -> no running process matches /{pattern}/")
        return
    if dry_run:
        print(f"  -> would stop {len(pids)} process(es) matching /{pattern}/: {' '.join(pids)}")
        return
    subprocess.run(["kill", *pids], check=False)
    print(f"  -> stopped {len(pids)} process(es) matching /{pattern}/")


def collect_global_state() -> dict[str, list[str]]:
    """server name -> client names that currently enable it."""
    active: dict[str, list[str]] = {}
    for client, path in global_targets():
        if not path.exists():
            continue
        try:
            data = read_config(path)
        except ToolError as exc:
            print(f"  !! {exc}", file=sys.stderr)
            continue
        for name in data.get("mcpServers", {}):
            active.setdefault(name, []).append(client)
    return active


def cmd_list(args) -> int:
    servers = load_catalog()
    print(f"=== MCP Catalog ({CATALOG_FILE}) ===")
    if not servers:
        print("  (catalog is empty)")
        return 0
    active = collect_global_state()
    for name, info in sorted(servers.items()):
        clients = active.get(name, [])
        tag = f"[active in: {', '.join(clients)}]" if clients else "[inactive]"
        print(f"  * {name:<18} [{info.get('category', 'general'):<8}] {tag}")
        if info.get("description"):
            print(f"    {info['description']}")
        indicator = info.get("command") or info.get("url") or ""
        invocation = " ".join([str(indicator), *[str(arg) for arg in info.get("args", [])]])
        print(f"    -> {invocation.strip()}\n")
    return 0


def cmd_status(args) -> int:
    print("=== Global MCP clients ===")
    for client, path in global_targets():
        if not path.exists():
            print(f"  * {client:<13} (not present: {path})")
            continue
        try:
            data = read_config(path)
        except ToolError as exc:
            print(f"  !! {exc}", file=sys.stderr)
            continue
        names = list(data.get("mcpServers", {}))
        detail = f"{len(names)} server(s): {', '.join(names)}" if names else "0 servers"
        print(f"  * {client:<13} {detail}")

    project = Path.cwd() / ".mcp.json"
    print(f"\n=== Current project ({Path.cwd()}) ===")
    if not project.exists():
        print("  * .mcp.json: not present")
        return 0
    try:
        data = read_config(project)
    except ToolError as exc:
        print(f"  !! {exc}", file=sys.stderr)
        return 1
    names = list(data.get("mcpServers", {}))
    detail = f"{len(names)} server(s): {', '.join(names)}" if names else "0 servers"
    print(f"  * .mcp.json: {detail}")
    return 0


def cmd_enable(args) -> int:
    servers = load_catalog()
    if args.name not in servers:
        raise ToolError(f"server '{args.name}' is not in the catalog; run 'list' to see what is")
    definition = server_definition(servers[args.name], args.name)

    print(f"=== Enabling '{args.name}' globally{' (dry-run)' if args.dry_run else ''} ===")
    failures = 0
    for client, path in global_targets():
        if not path.exists() and not args.create:
            print(f"  - {client:<13} skipped: {path} is not present (--create to make it)")
            continue
        try:
            data = read_config(path)
        except ToolError as exc:
            print(f"  !! {exc}", file=sys.stderr)
            failures += 1
            continue
        mcp_servers = data.setdefault("mcpServers", {})
        if mcp_servers.get(args.name) == definition:
            print(f"  = {client:<13} already enabled")
            continue
        mcp_servers[args.name] = definition
        write_config(path, data, backup=True, dry_run=args.dry_run)
        print(f"  + {client:<13} {'would write' if args.dry_run else 'enabled'} {path}")

    if args.kill:
        stop_processes(definition, args.name, args.dry_run)
    print(f"=== Enabling '{args.name}' complete ===")
    return 1 if failures else 0


def cmd_disable(args) -> int:
    # The catalog is optional here: disabling must work for entries that were
    # removed from the catalog but are still configured somewhere.
    try:
        servers = load_catalog()
    except ToolError:
        servers = {}

    print(f"=== Disabling '{args.name}' globally{' (dry-run)' if args.dry_run else ''} ===")
    failures = 0
    for client, path in global_targets():
        if not path.exists():
            print(f"  - {client:<13} skipped: {path} is not present")
            continue
        try:
            data = read_config(path)
        except ToolError as exc:
            print(f"  !! {exc}", file=sys.stderr)
            failures += 1
            continue
        mcp_servers = data.get("mcpServers", {})
        if args.name not in mcp_servers:
            print(f"  = {client:<13} not enabled")
            continue
        del mcp_servers[args.name]
        if not mcp_servers:
            data.pop("mcpServers", None)
        write_config(path, data, backup=True, dry_run=args.dry_run)
        print(f"  + {client:<13} {'would write' if args.dry_run else 'disabled'} {path}")

    if args.kill:
        if args.name in servers:
            definition = server_definition(servers[args.name], args.name)
            stop_processes(definition, args.name, args.dry_run)
        else:
            print(f"  -> '{args.name}' is not in the catalog, so its command is unknown; "
                  f"no process was stopped")
    print(f"=== Disabling '{args.name}' complete ===")
    return 1 if failures else 0


def project_mcp_file(args) -> Path:
    return (Path(args.dir).resolve() if args.dir else Path.cwd()) / ".mcp.json"


def cmd_attach(args) -> int:
    servers = load_catalog()
    if args.name not in servers:
        raise ToolError(f"server '{args.name}' is not in the catalog")
    definition = server_definition(servers[args.name], args.name)

    mcp_file = project_mcp_file(args)
    data = read_config(mcp_file)
    mcp_servers = data.setdefault("mcpServers", {})
    if mcp_servers.get(args.name) == definition:
        print(f"'{args.name}' is already attached in {mcp_file}")
        return 0
    mcp_servers[args.name] = definition
    write_config(mcp_file, data, backup=False, dry_run=args.dry_run)
    print(f"=== {'Would attach' if args.dry_run else 'Attached'} '{args.name}' to {mcp_file} ===")
    return 0


def cmd_detach(args) -> int:
    mcp_file = project_mcp_file(args)
    if not mcp_file.exists():
        print(f"No .mcp.json in {mcp_file.parent}")
        return 0
    data = read_config(mcp_file)
    mcp_servers = data.get("mcpServers", {})
    if args.name not in mcp_servers:
        print(f"'{args.name}' is not attached in {mcp_file}")
        return 0
    del mcp_servers[args.name]
    if not mcp_servers:
        data.pop("mcpServers", None)
    write_config(mcp_file, data, backup=False, dry_run=args.dry_run)
    print(f"=== {'Would detach' if args.dry_run else 'Detached'} '{args.name}' from {mcp_file} ===")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp_tool.py",
        description="SSOT manager for Model Context Protocol (MCP) servers",
    )
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    parser.add_argument(
        "--create",
        action="store_true",
        help="also write to global client configs that do not exist yet",
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="after enabling or disabling, stop processes matching the server's own command line",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("list", help="list catalog servers and where they are active")
    subparsers.add_parser("status", help="show MCP servers per client and per project")

    enable = subparsers.add_parser("enable", help="enable a server in every present client")
    enable.add_argument("name")

    disable = subparsers.add_parser("disable", help="remove a server from every present client")
    disable.add_argument("name")

    attach = subparsers.add_parser("attach", help="attach a server to a project's .mcp.json")
    attach.add_argument("name")
    attach.add_argument("dir", nargs="?", default=".", help="project directory (default: .)")

    detach = subparsers.add_parser("detach", help="detach a server from a project's .mcp.json")
    detach.add_argument("name")
    detach.add_argument("dir", nargs="?", default=".", help="project directory (default: .)")

    return parser


COMMANDS = {
    "list": cmd_list,
    "status": cmd_status,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "attach": cmd_attach,
    "detach": cmd_detach,
}


def main() -> int:
    args = build_parser().parse_args()
    try:
        return COMMANDS[args.subcommand](args)
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; no further changes were made.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
