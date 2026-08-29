# Routing protocol

Route on what you actually know. Relative cost, speed, capability, and
authorization are stable and observable; remaining subscription balance is not.
Assign roles from the former and treat quota as a constraint on the result.

## Cost arbitrage

The durable routing rule is a division of labor by price and speed rather than a
ranking of vendors:

- Spend the expensive, strongest context on the work that decides the outcome:
  understanding the problem, freezing the contract, writing withheld checks, and
  adjudicating disputed evidence.
- Give high-frequency iteration — compile, test, fix, repeat — to the cheapest
  provider that can carry it, because that loop consumes the most tokens per unit
  of progress and benefits least from a stronger model.
- Keep the reviewer in a different engine family from the implementer when an
  eligible one exists, so a shared blind spot is less likely.

This holds without any telemetry, which is why it belongs in the protocol while
balance-based scheduling does not.

## Provider profile

The host should supply a current profile equivalent to:

```yaml
provider: example-cli
ready: true
roles: [investigate, implement, review]
write_authorized: false
relative_cost: low
relative_speed: fast
engine_family: example
strengths: [large-repository-search, long-running-implementation]
limits: [no-background-mode]
last_verified_version: 1.2.3
```

Store mutable profiles outside the Skill. Never store login material, API keys,
or private endpoints in a provider profile.

## Assignment order

Apply these rules lexicographically:

1. **Authorization:** exclude providers whose use or side effects are not
   authorized.
2. **Readiness:** exclude missing, logged-out, or contract-unknown providers from
   critical roles. A safe local smoke outranks documentation claims.
3. **Quality floor:** exclude providers that cannot produce or verify the
   required artifact.
4. **Cost arbitrage:** among eligible providers, match role to relative cost and
   speed as above.
5. **Independence:** prefer an engine-diverse reviewer over the implementer.
6. **Cycle time:** break remaining ties using background capability, startup
   latency, context-transfer cost, and current queue depth.

Do not hide a provider switch. Record the reason in the run receipt.

## Quota as a constraint

Quota bounds the plan; it does not choose the work.

- Respect known hard limits, and avoid exhausting a provider the run will need
  later for a role no one else can fill.
- When the user or host supplies a remaining fraction or a qualitative pressure,
  use it only to break a tie that the rules above left open, and say that the
  route was estimate-based. `unknown` must remain unknown.
- Do not infer an account's remaining allowance from one call's reported usage,
  which describes that call alone.
- Do not generate work to consume capacity. Idle quota costs nothing; a review
  round spent on manufactured work costs the coordinator's attention, which is
  the scarce resource.

## Cost of a role

Independent review is not a cheap afterthought. A review brief carries expected
values, reproduction steps, and withheld checks that the implementer never
received, so it can cost several times the context of the task contract it
judges. Budget the reviewer as a first-class consumer of quota, and do not
schedule a review round on the assumption that it is a quick look at a diff.
