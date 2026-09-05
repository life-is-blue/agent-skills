# agent-skills

Portable Agent Skills for coding and document workflows. Each
`skills/<name>/SKILL.md` is the entrypoint; copy the complete Skill directory so
its scripts and references remain available.

## Skills

| Skill | Type | Purpose |
|---|---|---|
| `branded-pptx` | bundled | Build decks from an outline on your own .pptx template, with layout verification |
| `coding-agent` | adapter | Run Codex, Claude Code, TClaude, CodeBuddy Code, or OpenCode as monitored background workers, with a structured Codex mode returning a machine-readable result envelope |
| `office-mpp` | bundled | Read, analyze, export, create, and edit Microsoft Project or MSPDI files |
| `openclaw-coding-agent` | adapter | Run supported coding CLIs through OpenClaw sessions and notifications |
| `pdf-to-markdown` | protocol-only | Guide a host-provided PDF-to-Markdown workflow |
| `search-docs` | adapter | Search and read the git-library documentation service |
| `skill-evolve-lite` | protocol-only | Improve a Skill through train traces, validation gates, and rollback |
| `verified-dev-loop` | protocol-only | Coordinate delegated implementation and evidence-based acceptance as a durable development loop |
| `wechat-publish` | protocol-only | Guide a host-provided WeChat publishing workflow |

The machine-readable list and delivery type are in
[`skills/catalog.json`](skills/catalog.json). `bundled` includes the core
implementation, `adapter` includes an integration with an external CLI or API,
and `protocol-only` requires the host project to provide the implementation.

## Verified development loop

`verified-dev-loop` is a control-plane protocol for the coordinating agent. The
coordinator owns scope, contracts, acceptance evidence, plan state, and stop
decisions. Native subagent APIs or CLI adapters carry role-specific work and
return artifacts; they do not decide what should pass. Implementers receive the
frozen task contract, while reviewers receive the candidate and a separate
review contract, including any checks withheld from the implementer.

```mermaid
flowchart TB
    U[User<br/>judgment and external-effect gates]

    subgraph control[Control plane]
        C[Coordinator<br/>verified-dev-loop]
        S[(Role-visible repository state<br/>run · constraints · ledger · contracts)]
        P[(Host-private state<br/>withheld checks · raw logs)]
        S -->|read constraints, plan, and gates| C
        P -->|private evidence| C
    end

    subgraph transport[Host transport]
        A[Native subagent API or CLI adapter]
    end

    subgraph roles[Execution roles]
        I[Implementer]
        R[Reviewer]
    end

    U <--> C
    C -->|frozen task or narrow repair<br/>plus result path| A
    A -->|dispatch| I
    I -->|implementation envelope| A
    A -->|transport envelope| C
    C -->|review contract and withheld checks| A
    A -->|dispatch| R
    R -->|review verdict envelope| A
    A -->|transport envelope| C
    A -->|raw logs| P
    C -->|go: advance ledger| S
    C -->|no-go: issue narrow repair| A
```

The Skill remains `protocol-only`: it does not bundle a runner. A host can use
the repository's `coding-agent` adapter, another monitored
CLI adapter, or a native subagent API to implement the transport layer. A
multi-round run defaults to `.verified-dev-loop/<run-id>/` for role-visible
state; withheld checks and raw transport state stay outside the repository.
Transport success, implementation delivery, and acceptance are three separate
claims, and only the coordinator advances the run state.

## Install

```bash
git clone https://github.com/life-is-blue/agent-skills.git
cp -r agent-skills/skills/<name> <client-skill-directory>/
```

Read the copied `SKILL.md` before use. Client discovery directories and symlink
support vary, so verify them against the current client and a local smoke test.

## Validate

```bash
python3 scripts/validate_repo.py
python3 -m pytest -q
```

Repository changes follow [`AGENTS.md`](AGENTS.md). The default repository
license is [MIT](LICENSE); retained upstream material is listed in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
