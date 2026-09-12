# MCP Registry & Management (SSOT)

Declarative Model Context Protocol (MCP) server catalog and
single-source-of-truth management tooling.

## Philosophy

- **Decoupled Definitions**: All reusable MCP server configurations live here
  in [`catalog.json`](catalog.json), versioned in Git. Secrets never do — see
  the environment variables section below.
- **Project-Level First**: Prefer attaching MCP servers locally to specific
  projects (`.mcp.json`) rather than polluting global client environments.
- **One-Command Toggling**: When global access is required, enable or disable
  servers across all AI clients (Claude Code, CodeBuddy, Gemini/Antigravity)
  with a single command.

## Environment variables

Credential-bearing entries reference environment variables instead of embedding
values. Export them before enabling those servers; the tool fails with a clear
error rather than writing a literal `${...}` into a client config.

| Variable | Used by | Notes |
|---|---|---|
| `WECOM_DOC_APIKEY` | `wecom-doc` | WeCom robot document API key |
| `CONTEXT7_SSE_ID` | `context7` | Tencent Cloud Context SSE endpoint id |
| `FIGMA_TOKEN` | `figma` | Figma personal access token |
| `DB_PATH` | `sqlite` | Optional; defaults to `./data.db` |
| `CODEBUDDY_IDE_MCP_SETTINGS` | codebuddy-ide target | Optional override for the IDE config path |

## Quickstart

```bash
# List all catalog servers and where each is currently active
./scripts/mcp_tool.py list

# View active MCP servers across clients and the current project
./scripts/mcp_tool.py status

# Preview any change without writing it
./scripts/mcp_tool.py --dry-run enable figma

# Attach an MCP server locally to the current project (.mcp.json)
./scripts/mcp_tool.py attach chrome-devtools

# Detach an MCP server from the current project
./scripts/mcp_tool.py detach chrome-devtools

# Enable an MCP server globally across all present clients
./scripts/mcp_tool.py enable figma

# Disable globally, and also stop processes started from its own command line
./scripts/mcp_tool.py --kill disable figma
```

By default only clients that already have a config file are touched; a client
that is not installed is reported and skipped. Pass `--create` to write to
missing global configs deliberately. Process termination is opt-in via `--kill`.

## Safety

Client config files hold far more than their MCP block (`~/.claude.json` also
holds projects, history and settings), so:

- A config that cannot be parsed is reported and **left untouched**; the tool
  never falls back to an empty document, because writing one would delete every
  unrelated setting.
- Writes are atomic (temp file plus rename), so an interrupted run cannot leave
  a half-written config.
- Global client configs are copied to `<name>.bak` before being replaced.
  Project `.mcp.json` files are not backed up: git already holds the previous
  revision, and a stray `.mcp.json.bak` in a repository is noise.
- `--kill` matches the server's own command line, not its catalog name, so
  `disable figma` cannot take down an unrelated program that merely mentions
  "figma".

## Adding a New Server

Add the server definition to [`catalog.json`](catalog.json) under `servers`. Use
`${VAR}` (or `${VAR:-default}`) for anything credential-bearing:

```json
"my-service": {
  "command": "uvx",
  "args": ["my-mcp-server", "--token", "${MY_SERVICE_TOKEN}"],
  "category": "database",
  "description": "Short description of what this MCP server does"
}
```

`category` and `description` are catalog metadata; they are stripped before the
definition is written into a client config.
