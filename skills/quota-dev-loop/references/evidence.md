# Evidence provenance

The initial protocol was derived from a local, non-bundled development corpus
covering a multi-agent Rust rewrite between 2026-08-21 and 2026-08-23. Raw
content is intentionally excluded because it contains private repository and
session context.

| Role in corpus | Artifact SHA-256 | Supported observation |
|---|---|---|
| Coordinator and task-book authoring | `fb65b4f91d59993b95ea15fdc2fedf9639f4cd726d0c438e420e37966ed9809d` | Repeated bounded task books reduced context transfer; the coordinator still had to resolve mistaken premises and decide the next phase. |
| Agy implementation trajectory | `5a29dae1206416c3df0fefd39e14b9057e676864b8eabbdb444ee8c0fc94c8da` | Frozen goals, editable boundaries, progress files, retry limits, and machine checks supported long resumable implementation. |
| Codex acceptance trajectory | `a9aa79afb257cc0e3a82f654a4c65bddf55cbfdfefbcd005298ccffac6dc01b9` | Independent reruns and adversarial checks found issues not established by implementer summaries alone. |

Additional local implementation evidence came from a separate multi-CLI router
whose adapters demonstrated that provider success envelopes, permissions,
background behavior, and exit semantics cannot safely be assumed uniform.

## Limits of the evidence

- The main corpus is one project and is weighted toward a high-risk refactor.
- It contains no randomized comparison against a single-agent workflow.
- It supports the role separation and contract mechanisms as plausible reusable
  rules, but does not establish that every task needs three providers.
- It does not provide reliable remaining-quota telemetry for any subscription.

Use run receipts from new projects to test these rules across fast, standard,
and deep modes before claiming general throughput improvement.
