# ADR-0015: No-write enterprise dry-run and review boundary

- Status: Accepted
- Date: 2026-07-25
- Scope: ENT-D, synthetic fixture-only validation and review artifacts

## Context

ENT-B creates versioned candidates and explicit mapping dispositions. ENT-C reconciles paged source
records into a deterministic checkpoint. Neither stage tells an operator what would be created,
changed, or removed from a canonical snapshot, nor does it combine mapping coverage, source quality,
freshness, and quarantine into one reviewable artifact.

The local environment cannot authorize company data, a vendor API, a real ACL evaluator, or writes to
the canonical PostgreSQL store. A safe preparation stage must therefore make proposed impact visible
without turning candidate acceptance into import authority.

## Decision

ENT-D accepts three contracts:

```text
enterprise-dry-run-input.v1
enterprise-resolution-file.v1
enterprise-dry-run-report.v1
```

The dry-run input contains a synthetic canonical snapshot, candidate-kind key rules, an explicit
`as_of`, freshness threshold, known opaque ACL references, and quality probes. It is not a canonical
repository export or an ACL grant.

```text
CanonicalChangeAction = CREATE | UPDATE | DELETE | NO_CHANGE
EnterpriseDryRunStatus = READY_FOR_REVIEW | BLOCKED
```

The engine compares each current ENT-C source state with a source-linked snapshot object. Active
candidates produce create, update, or no-change proposals. `DELETED` and `RESTRICTED` states produce a
delete proposal only when a linked snapshot object exists. Every proposal contains before/after
values, stable source identity, mapping reasons, and a deterministic change ID.

The report always fixes:

```text
write_performed = false
canonical_import_authorized = false
```

`READY_FOR_REVIEW` means no blocking quality finding remains in the input. It still does not authorize
an import.

## Quality and quarantine policy

Canonical quality codes are:

```text
DANGLING_REFERENCE
TIME_AMBIGUITY
UNMAPPED_FIELD
ACL_REFERENCE_UNKNOWN
STALE_SOURCE
MAPPING_QUARANTINED
MAPPING_REJECTED
```

Every finding has severity, stable finding ID, source identity/hash when available, and an explicit
`blocks_import` flag. Mapping ambiguity, dangling references, time ambiguity, and unknown ACL
references block import. Unmapped extra fields and stale source state remain visible warnings.
An exact duplicate rejected by ENT-B is informational and does not create a blocking quarantine.

Each blocking finding becomes a deterministic quarantine entry. One bad source does not discard
valid canonical-change proposals or unrelated findings. Quarantine is embedded in the report artifact;
ENT-D adds no database queue.

The report summary exposes record count, mapped count and coverage, change counts, finding count,
rejected/quarantined counts, open/proposed-resolution counts, and deterministic freshness seconds.

## Resolution boundary

```text
EnterpriseQuarantineStatus = OPEN | RESOLUTION_PROPOSED
EnterpriseResolutionAction =
  EXCLUDE_SOURCE | SOURCE_FIXED | MAPPING_UPDATED | ACKNOWLEDGE_RISK
```

A resolution file is reviewer input. It must reference a current deterministic quarantine ID and may
pin the source content hash. Unknown or stale references fail validation. A matching entry changes
only the queue state to `RESOLUTION_PROPOSED`; it cannot mark the source imported, approved, or
resolved. The source or mapping must be changed and dry-run rerun before a later import stage can use
it.

## CLI boundary

```text
soc-ot enterprise validate-source
soc-ot enterprise dry-run --output <report.json>
```

`validate-source` validates versioned registry, dirty corpus, sync corpus, dry-run input, and
resolution contracts. `dry-run` executes ENT-C in memory and writes only the requested JSON report.
Neither command opens the runtime database or vendor transport.

## Authority and operation boundaries

- A dry-run change is a proposal over candidate-shaped values, not a validated domain aggregate.
- No canonical Project/Event repository is read or written.
- No real ACL decision is made; an opaque reference is only checked against the supplied review list.
- No company field, tenant, user/group, credential, authentication, retention, or write-back is added.
- ENT-E owns synthetic principal/ACL exposure rules, redaction, lag/rate-limit/partial-source recovery,
  and health/metrics contracts.
- C0/C1 own actual company environment discovery, authorized sanitized data, adapter implementation,
  real ACL evaluation, and read-only pilot approval.

## Rejected alternatives

- Importing accepted candidates during dry-run: contradicts review-before-write and bypasses domain
  validation.
- Treating one mapping error as batch failure: hides valid proposed changes and makes remediation
  harder.
- Silently ignoring unknown payload fields: prevents mapping coverage review.
- Treating a resolution file as approval: gives an offline text artifact authority it does not have.
- Adding PostgreSQL quarantine now: couples ENT-D quality policy to a persistence design before the
  company environment is known.

## Verification gate

ENT-D passes only when the source-validation and dry-run CLI work from synthetic fixtures, canonical
change counts are deterministic, all required quality classes are explicit, one bad source preserves
valid proposals, stale/unknown resolution references fail, the report cannot set either write or
import authority true, no runtime database is opened, fixture hashes and generated contracts are
current, and full non-PostgreSQL regression plus repository boundary checks pass.
