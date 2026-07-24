# ADR-0012: Source-neutral enterprise ingestion boundary

- Status: Accepted
- Date: 2026-07-24
- Scope: ENT-A, synthetic fixture-only enterprise preparation

## Context

The local product reconstructs `DevelopmentProject` aggregates from validated synthetic fixtures.
Connecting a company source directly to that aggregate would collapse external identity, source time,
access control, deletion, mapping, and canonical truth into one unsafe step. It would also make the
application depend on one vendor's SDK before the source semantics are known.

ENT-A needs a stable boundary that can be implemented and tested outside the company network. It must
not introduce a live connector, company field identifiers, credentials, authentication, real
principal ACLs, canonical mapping, synchronization, or write-back.

## Decision

All future enterprise source adapters first produce a validated
`enterprise-source-record.v1`. The envelope contains:

- stable identity: `source_system`, `source_tenant`, `source_object_type`, `external_id`
- source change identity: `external_version` and lowercase SHA-256 `content_hash`
- four timezone-aware times: `effective_at`, `observed_at`, `source_updated_at`, `ingested_at`
- read-only provenance: `source_url`
- access metadata: opaque `source_acl_ref` and `classification`
- source availability: `deletion_state`
- source-neutral JSON object `payload` only while the record is `ACTIVE`

Stable identity excludes title, URL, source version, content hash, and payload. Rename, update, and
delete records therefore retain the same identity. `DELETED` and `RESTRICTED` records cannot carry
payload, preventing stale or restricted content from crossing the envelope boundary.

The classifications are:

```text
SourceDataClassification = PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED
SourceDeletionState       = ACTIVE | DELETED | RESTRICTED
```

The four times are deliberately not collapsed or ordered by the contract:

- `effective_at`: when the represented business state applies
- `observed_at`: when the organization could observe that state
- `source_updated_at`: the timestamp asserted by the source system
- `ingested_at`: when the twin captured this envelope

A planned state may be observed before it becomes effective, while late data may be ingested long
after it becomes effective. Clock and ordering anomalies are explicit mapping/quality outcomes in
ENT-B/ENT-D, not silently rewritten by ENT-A.

Application ports are dependency-inverted:

```text
SourceReader.read(identity) -> EnterpriseSourceRecord | None
IngestionSink.write(record) -> None
```

These ports accept only the validated envelope. `IngestionSink` stages a source record; it does not
create or mutate canonical Project, Issue, Risk, Evidence, Event, Decision, or FACT state.

## Authority and information boundaries

- Agent, Chair, and `ObservableCasePacket` do not receive raw enterprise records.
- `source_acl_ref` is an opaque reference, not a copied user/group list or an authorization decision.
- No HTTP endpoint, database table, migration, Frontend surface, or source adapter is added in ENT-A.
- No vendor SDK or vendor-specific object type becomes an application/domain dependency.
- Mapping structured fields and extracting unstructured candidates belong to ENT-B.
- Cursor, retry, tombstone reconciliation, and incremental synchronization belong to ENT-C.
- Dry-run, quarantine, quality reporting, and resolution belong to ENT-D.
- Authentication and real ACL enforcement remain internal C0 scope; write-back remains C2.

## Consequences

- Source identity and time semantics can be tested before company access exists.
- Missing ACL/classification fails validation instead of defaulting to broad visibility.
- Deleted or restricted source content cannot be retained in the envelope payload.
- Canonical Project truth remains unchanged until a later validated mapping and review path exists.
- ENT-B can add synthetic dirty exports and mapping candidates without changing this envelope's major
  version unless it changes a required field or field meaning.

## Rejected alternatives

- Direct source-to-`DevelopmentProject` conversion: hides identity, time, ACL, deletion, and mapping
  failures inside canonical state.
- Jira- or Confluence-specific application models: couple the core to an unverified vendor schema.
- One generic timestamp: cannot distinguish business effectiveness, organizational observability,
  source modification, and ingestion delay.
- Copying concrete user/group ACLs into the public/local PoC: requires company identity and security
  policy that are unavailable outside C0.
- Keeping payload on deleted/restricted records: can leak content after deletion or access reduction.
- Adding cursor/page-token contracts now: belongs to ENT-C and would guess at synchronization behavior.

## Verification gate

ENT-A is complete only when the ADR and canonical vocabulary are synchronized, the strict Pydantic
contract and source-neutral ports pass positive and negative tests, generated JSON Schema is current,
vendor/framework boundary scans pass, and the full non-PostgreSQL regression passes. PostgreSQL,
Frontend, and browser behavior are unchanged by this contract-only stage.
