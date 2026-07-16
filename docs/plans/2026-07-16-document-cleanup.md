# Document cleanup

## Goal

Reduce documentation noise while preserving current operational truth in each
Skill and keeping historical material clearly separated.

## Decisions

- Move the April 2026 `office-mpp` audit bundle to
  `docs/archive/office-mpp-audits/`; do not delete it in this change.
- Mark archived audits as historical and potentially stale. Current scripts,
  tests, `SKILL.md`, and references take precedence.
- Keep the identical MSPDI template and test fixture because they serve
  different interfaces and should not be coupled.
- Keep the per-Skill license because Skills are copied and distributed
  independently.

## Follow-up cleanup candidates

1. Delete the duplicate `office-mpp/README.md`; `SKILL.md` is the entrypoint.
2. Replace `references/maintenance.md` with direct links to the existing
   report, diff, and convert references; stop presenting `mpp_analyze.py` as a
   CLI because it is an internal module.
3. Remove placeholder-only tests so the passing test count reflects real
   behavior; retain missing coverage as explicit test debt.
4. Trim protocol-only Skills to host-facing contracts. Remove implementation
   internals that are neither shipped nor executable from this repository.
5. Shorten `office-mpp/SKILL.md` to routing, invariants, and reference links;
   keep detailed flags and schemas in references.

## Acceptance for archive step

- No `AUDIT_*` or `README_AUDIT.md` files remain under `skills/office-mpp/`.
- All five audit files are preserved under the archive directory.
- The archive contains a notice that it is not current product documentation.
- Repository validation and tests still pass.
