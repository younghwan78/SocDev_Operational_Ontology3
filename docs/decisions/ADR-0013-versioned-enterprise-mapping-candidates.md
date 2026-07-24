# ADR-0013: Versioned enterprise mapping candidates and dirty-source disposition

- Status: Accepted
- Date: 2026-07-25
- Scope: ENT-B, synthetic fixture-only mapping preparation

## Context

ENT-A validates source identity, time, access metadata, deletion state, and JSON payload without
creating canonical truth. The next boundary must describe how a validated source record can become a
reviewable Project/WorkItem/Issue/Evidence/Event candidate while preserving where every value came
from.

Real enterprise exports are not clean or ordered. A useful local preparation must exercise missing
fields, unknown statuses, duplicate versions, out-of-order arrival, moved URLs, deletions, access
restriction, conflicting content, and late evidence without inventing company fields or connecting a
vendor API.

## Decision

ENT-B introduces three versioned contracts:

```text
enterprise-mapping-registry.v1
enterprise-mapping-result.v1
enterprise-dirty-fixture-corpus.v1
```

The registry resolves an exact `(source_system, source_object_type)` to one profile. Each profile
fixes `profile_id`, `mapping_version`, required source fields, direct field mappings, optional status
mapping, unstructured extraction rules, and a late-arrival threshold. Duplicate profile IDs or source
keys are invalid.

Mapping produces candidates, never canonical aggregates:

```text
StructuredCandidateKind   = PROJECT | WORK_ITEM | ISSUE | EVIDENCE | EVENT
UnstructuredCandidateKind = CLAIM | RISK | ASSUMPTION
CandidateReviewStatus     = UNREVIEWED
```

Every structured candidate carries source identity/version, mapping profile/version, mapped values,
and at least one JSON-pointer source span. Every unstructured candidate additionally carries an
extractor version and character offsets. An unstructured candidate cannot claim `FACT` or a reviewed
state. The deterministic synthetic extractor records no invented confidence value.

Every record receives exactly one mapping disposition:

```text
MappingDisposition = ACCEPT | QUARANTINE | REJECT
```

- `ACCEPT` means candidate generation succeeded. It does not authorize canonical import.
- `QUARANTINE` means source ambiguity or conflict requires later resolution.
- `REJECT` means the record must not generate a candidate, such as an exact duplicate or missing
  profile.

The canonical reason codes are:

```text
MAPPED
PROFILE_NOT_FOUND
REQUIRED_FIELD_MISSING
STATUS_UNMAPPED
DUPLICATE_SOURCE_VERSION
SOURCE_VERSION_CONFLICT
OUT_OF_ORDER_SOURCE_UPDATE
SOURCE_URL_CHANGED
SOURCE_DELETED
SOURCE_RESTRICTED
LATE_ARRIVAL
```

An exact repeated identity/version/hash is rejected as a duplicate. Reusing the same identity/version
with a different hash is quarantined. A later-ingested record with an older source-update time is
quarantined. A URL move and late arrival remain accepted with explicit reason codes.

Deleted and restricted records contain no payload under ENT-A. ENT-B therefore emits only a
metadata-only `EVENT` candidate. Applying tombstones or access reduction to canonical state remains
ENT-C work.

## Synthetic corpus

The committed corpus uses only `synthetic-work-tracker` and `synthetic-knowledge-base`. It covers one
normal case and all nine declared dirty patterns:

```text
MISSING_FIELD
UNKNOWN_STATUS
DUPLICATE_UPDATE
OUT_OF_ORDER_EVENT
MOVED_PAGE
DELETED_OBJECT
RESTRICTED_OBJECT
CONFLICTING_SOURCE
LATE_EVIDENCE
```

The registry and corpus are SHA-256 pinned by `fixtures/enterprise/manifest.yaml`. They contain no
company field ID, tenant, URL, principal, credential, or vendor-specific application dependency.

## Authority and operation boundaries

- A mapping candidate is not a `DevelopmentProject`, domain object, Project projection, or FACT.
- Mapping does not write a repository, database, API, Frontend, Agent packet, or company system.
- `ACCEPT` does not mean human approval or successful import.
- ENT-C owns cursor, retry, idempotent replay, tombstone application, and reconciliation.
- ENT-D owns dry-run CLI, canonical diff, persisted quarantine/resolution, and quality reporting.
- Real authentication and ACL evaluation remain C0; write-back remains C2.

## Consequences

- Normal and dirty records receive explicit, reproducible outcomes rather than silent loss.
- Mapping/status changes are reviewable through versioned profiles.
- Source spans make every candidate traceable to exact source fields or text offsets.
- Unstructured extraction cannot silently promote prose to FACT.
- Later sync and dry-run stages can consume mapping results without changing canonical Project models.

## Rejected alternatives

- Mapping directly into domain models: conflates candidate generation with canonical validation and
  import authority.
- Free-form dictionaries without a profile contract: cannot reproduce status or field decisions.
- Treating all dirty records as errors: loses valid moved, deleted, restricted, and late-arriving
  operational signals.
- Treating all dirty records as accepted: hides ambiguity and conflicting source versions.
- LLM extraction in ENT-B: adds nondeterminism and provider/data boundaries before provenance and
  human review are ready.
- Implementing a durable quarantine queue now: belongs to ENT-D.

## Verification gate

ENT-B is complete only when the mapping/candidate/corpus contracts and canonical terms agree,
generated schemas are current, every corpus case matches its frozen disposition/reason, source spans
and versions are mandatory, unreviewed text cannot become FACT, fixture hashes and boundary scans
pass, and the full non-PostgreSQL regression passes. This contract-only stage does not require a
database migration, Frontend change, or browser workflow.
