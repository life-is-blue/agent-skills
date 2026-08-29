# Evidence provenance

The initial protocol was derived from a local, non-bundled development corpus
covering a multi-agent Rust rewrite between 2026-08-21 and 2026-08-23. Raw
content is intentionally excluded because it contains private repository and
session context.

| Role in corpus | Artifact SHA-256 | Records |
|---|---|---|
| Coordinator, contract authoring, withheld checks | `fb65b4f91d59993b95ea15fdc2fedf9639f4cd726d0c438e420e37966ed9809d` | 405 |
| Implementation trajectory | `5a29dae1206416c3df0fefd39e14b9057e676864b8eabbdb444ee8c0fc94c8da` | 5399 |
| Independent acceptance trajectory | `a9aa79afb257cc0e3a82f654a4c65bddf55cbfdfefbcd005298ccffac6dc01b9` | 302 |

## Measured observations

Counts below are recoverable from the artifacts above. Character counts are
measured on the coordinator artifact, which stores its messages in full; the
implementation artifact elides the middle of long messages and understates any
length measured from it.

- **Withheld checks did the detection work.** Of 31 verdicts recording both
  scores, the visible acceptance commands were incomplete in 5, while the
  checks withheld from the implementer were incomplete in 17. In 15 of those
  rounds — roughly half of all rounds — the implementer scored full marks on
  every check it could see and still failed on checks it could not. This is the
  strongest single result in the corpus and the reason withheld checks are
  required rather than optional.
- **What the withheld checks caught** was consistently the gap between a claim
  and its execution: a retry path that computed backoff intervals but never
  waited, a parameter documented as contract-driven but hard-coded, a delivery
  record asserting verification without the outputs that would show it, a
  business error that returned success, and a production identifier left in a
  file that simultaneously claimed zero occurrences.
- **First-pass acceptance was 41%** — 14 accepted against 20 rejected across 34
  relayed verdicts. Multi-round repair was the normal case, not the exception.
- **Review was cheap to author and expensive to run.** The 31 review briefs
  measured a median of 1106 characters, about 0.45 times the contract they
  judged, because a brief points at a judge and its expected values instead of
  restating a specification. The acceptance rounds themselves took 1m50s to 15
  minutes of wall clock, mostly 5 to 11 minutes, since the reviewer reran the
  suite and built its own harness. Review consumes capacity as execution, not as
  authoring.
- **Task contracts ran against a hard prompt bound.** 34 full contracts measured
  a median of 2704 and a maximum of 3859 characters against the 4000-character
  `/goal` limit declared by the Skill that authored them, so the largest consumed
  96% of the cap; 3 narrow repair contracts measured 723 to 1434. They were
  dispatched at a median interval of 18 minutes over a 37.5-hour span containing
  roughly 9.7 hours of active intervals. A fixed prompt bound against
  accumulating cross-round invariants is what makes restating them in every
  contract unaffordable.
- **The remaining plan was not durable.** The coordinator was asked twice in one
  run, roughly 65 messages apart, how many contracts were still needed to reach
  the objective. The plan existed only in its context, while the per-round
  receipt written into the repository covered the current task alone.
- **The read-back existed and was not a gate.** Every contract opened with a
  task 0 that verified baseline numbers before any edit, and half of them also
  required a written receipt of the goal as understood, the intended order, and
  the largest risk. Nothing acted on that receipt, and the round rejected over a
  contract defect rather than an implementation defect surfaced only after the
  work was finished and reviewed.
- **The reviewer was not infallible.** At least one rejection was itself wrong,
  overturned by the controller citing a specific file and line in the reference
  implementation, after which the contract was corrected instead of the working
  code.
- **Ground truth came from outside the implementer.** The resulting repository,
  which is local and not bundled here, carries 19 judge scripts and 21
  differential suites against the legacy engine, and its gate was stated as a
  rising count of passing cases with zero ignored.

Additional local implementation evidence came from a separate multi-CLI router
whose adapters demonstrated that provider success envelopes, permissions,
background behavior, and exit semantics cannot safely be assumed uniform.

## Limits of the evidence

- The corpus contains **no subscription-quota evidence at all**. Every quota
  reference in it is a third-party API rate limit, not an AI subscription
  balance. The stated motivations were context preservation and cost arbitrage
  between an expensive coordinator and a cheaper implementer, which is why
  routing here is based on cost and capability and quota is only a constraint.
  Any balance-based scheduling a host adds on top remains unvalidated.
- The main corpus is one project and is weighted toward a high-risk refactor.
- It contains no randomized comparison against a single-agent workflow, so the
  41% first-pass rate has no baseline to be measured against.
- It supports the role separation, ground-truth, and contract mechanisms as
  plausible reusable rules, but does not establish that every task needs three
  providers.
- Manual relay between providers was the dominant human cost in the corpus and is
  outside this Skill's scope; the protocol assumes a host runner exists.
- It does not provide reliable remaining-quota telemetry for any subscription.

Use run receipts from new projects to test these rules across fast, standard,
and deep modes before claiming general throughput improvement.
