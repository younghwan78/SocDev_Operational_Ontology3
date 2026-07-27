# ADR-0016: Synthetic enterprise security and operation emulator

- Status: Accepted
- Date: 2026-07-27
- Scope: ENT-E, fixture-only policy and recovery verification

## Context

ENT-A requires classification and an opaque ACL reference. ENT-D reports an unknown reference but
does not decide whether a principal may expose source content to a Frontend, API, model, Role packet,
or log. The local PoC also lacks a deterministic way to verify credential redaction, source freshness,
partial synchronization, rate limiting, readiness, metrics, and metadata-only audit.

Real authentication, company identity/group inheritance, vendor credentials, and production
observability are unavailable outside the company environment. ENT-E must therefore fix the behavior
a later adapter must satisfy without pretending that synthetic policy evaluation is real
authorization.

## Decision

ENT-E accepts:

```text
enterprise-security-operation-policy.v1
enterprise-security-operation-scenario-corpus.v1
enterprise-security-operation-report.v1
```

The policy defines synthetic principals/groups, opaque ACL allow/deny lists, classification-to-surface
exposure modes, sensitive field names, and lag/stale thresholds.

```text
EnterpriseExposureSurface = FRONTEND | API | MODEL | ROLE_PACKET | LOG
EnterpriseExposureMode    = FULL | METADATA_ONLY | DENY
EnterpriseAccessDecision  = ALLOW | DENY
```

Every classification rule covers every surface. `PUBLIC` and `INTERNAL` may expose full content on
user/model surfaces after ACL allow; logs receive metadata only. `CONFIDENTIAL` is denied to MODEL and
ROLE_PACKET by policy. `RESTRICTED` is denied on every surface.

Evaluation order is fail-closed:

1. restricted or inactive source,
2. classification denial,
3. unknown principal,
4. missing ACL,
5. explicit or conflicting deny,
6. no allow match,
7. allow with the classification surface mode.

Allow and deny applying together is `ACL_CONFLICT` and produces `DENY`. Reports retain only a SHA-256
source reference, not raw source identity, URL, or payload.

The report always fixes:

```text
real_authorization_performed = false
credential_persisted = false
```

## Redaction

Untrusted diagnostic messages, headers, and nested JSON payloads are redacted recursively. Configured
sensitive field names are replaced with `[REDACTED]`. Bearer values, token/password/secret/API-key
assignments, and URL user-info are redacted even when found in an otherwise safe field. The output
records only redacted paths and sanitized values.

Audit events contain event type, time, hashed subject reference, and compact outcome code. They do
not contain a raw source identity, payload, diagnostic body, or credential.

## Operation states and recovery

```text
EnterpriseIncidentType =
  HEALTHY | LAG | STALE | RATE_LIMITED | PARTIAL_SOURCE | UNKNOWN_FRESHNESS

EnterpriseHealthStatus    = HEALTHY | DEGRADED | NOT_READY
EnterpriseReadinessStatus = READY | NOT_READY

EnterpriseRecoveryAction =
  NONE | WAIT_BACKOFF | FULL_RECONCILIATION |
  RETRY_MISSING_PARTITION | ESCALATE_SOURCE_OWNER
```

Only a complete `HEALTHY` scenario with known freshness inside the lag threshold is READY and current.
Lag and recoverable rate limiting schedule backoff. Stale input requires full reconciliation.
Partial source retries the missing partition. Unknown freshness escalates to the source owner.
Unknown, partial, stale, lagged, or rate-limited source is never labeled current.

Metrics use fixed IDs for denied exposure count, redacted field count, partial-source count,
freshness-known, completion ratio, current flag, source lag seconds, and rate-limit retry seconds.
Metrics are data contracts only; ENT-E adds no Prometheus service or production alert.

## CLI boundary

```text
soc-ot enterprise emulate-security --output <report.json>
```

The command loads only synthetic policy/scenario fixtures, runs the emulator in memory, and writes
the requested report. It does not open the runtime database, authenticate a user, contact a source,
or modify canonical state.

## Authority and operation boundaries

- An `ALLOW` proves policy-fixture behavior, not a real access grant.
- No restricted payload enters the report, API, Frontend, Role packet, model input, log, or audit.
- No vendor credential, company user/group, inherited permission, or secret manager is implemented.
- No canonical import, durable queue, API route, Agent execution, or write-back is added.
- ENT-F owns templates, worksheets, runbook, rollback, and the external/internal handoff checklist.
- C0/C1 own real environment discovery, approved identity/ACL mapping, sanitized schema-fit, and
  read-only adapter implementation.

## Rejected alternatives

- Reusing opaque ACL references as authorization grants: the reference carries no evaluated meaning.
- Allow-on-missing or allow-on-conflict: violates fail-closed behavior.
- Logging raw source IDs for denied/restricted records: leaks the object the denial should protect.
- Redacting only header names: credentials can appear in nested payloads, messages, or URLs.
- Treating unknown freshness as stale-but-current: creates false operational confidence.
- Adding authentication middleware or monitoring infrastructure now: belongs to the approved company
  environment, not the fixture emulator.

## Verification gate

ENT-E passes only when every classification/surface and incident type is covered, frozen expected
exposure decisions match actual results, missing/unknown/conflicting ACL cases deny, restricted source
identity/content is absent from output and audit, all synthetic credential values are absent after
redaction, only one healthy scenario is current/ready, recovery metrics and events are deterministic,
the report cannot claim real authorization or credential persistence, the CLI opens no database,
fixture hashes/generated contracts are current, and full non-PostgreSQL regression plus repository
boundary checks pass.
