# Quota routing protocol

Quota-first means consuming the most perishable *eligible* capacity. It does not
mean assigning a weak or unauthorized provider to critical work.

## Provider profile

The host should supply a current profile equivalent to:

```yaml
provider: example-cli
ready: true
roles: [investigate, implement, review]
write_authorized: false
remaining_fraction: 0.70
resets_in_hours: 30
pressure: high
strengths: [large-repository-search, long-running-implementation]
limits: [no-background-mode]
last_verified_version: 1.2.3
```

Store mutable profiles outside the Skill. Never store login material, API keys,
or private endpoints in a provider profile.

When exact values exist, compare normalized quota pressure as:

```text
pressure = remaining_fraction / max(resets_in_hours / 24, 1 / 24)
```

The floor exists only to keep an imminent reset from dividing by zero; keep it
small enough that an hour from reset still outranks six hours from reset.

The value is a scheduling hint, not a cross-vendor token comparison. When exact
values do not exist, use the explicit qualitative pressure supplied by the user
or host. `unknown` must remain unknown.

## Cost of a role

Independent review is not a cheap afterthought. A review brief carries expected
values, reproduction steps, and withheld checks that the implementer never
received, so it can cost several times the context of the task contract it
judges. Budget the reviewer as a first-class consumer of quota, and do not
schedule a review round on the assumption that it is a quick look at a diff.

## Assignment order

Apply these rules lexicographically:

1. **Authorization:** exclude providers whose use or side effects are not
   authorized.
2. **Readiness:** exclude missing, logged-out, or contract-unknown providers from
   critical roles. A safe local smoke outranks documentation claims.
3. **Quality floor:** exclude providers that cannot produce or verify the
   required artifact.
4. **Quota pressure:** among eligible providers, prefer the quota closest to
   expiring with the greatest normalized remainder.
5. **Independence:** prefer an engine-diverse reviewer over the implementer.
6. **Cycle time:** break remaining ties using background capability, startup
   latency, context-transfer cost, and current queue depth.

Do not hide a provider switch. Record the reason in the run receipt.

## Useful overflow backlog

Maintain project-scoped tasks that can safely absorb quota without blocking the
main path:

- turn a historical defect into a regression test;
- probe an undocumented CLI or dependency failure shape in an isolated fixture;
- measure performance or coverage without changing production behavior;
- review recent diffs for security, concurrency, compatibility, or data-loss
  risks;
- identify stale documentation with exact file evidence;
- compare two designs and state what observation would choose between them.

Each item needs a bounded scope, an artifact, and a stop condition. Remove items
whose output no longer informs a decision.

## Missing quota telemetry

Most coding subscriptions do not expose a stable, safe, machine-readable quota
endpoint. Usage returned by a single CLI call describes that call, not the
account's remaining allowance. Until a provider offers verified telemetry,
require user input or a host-maintained estimate and label the resulting route
as estimate-based.
