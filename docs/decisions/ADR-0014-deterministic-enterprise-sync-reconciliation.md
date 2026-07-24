# ADR-0014: Deterministic enterprise sync and reconciliation

- Status: Accepted
- Date: 2026-07-25
- Scope: ENT-C, synthetic fixture-only synchronization

## Context

ENT-A validates source-neutral records and ENT-B maps them to reviewable candidates. Re-reading the
same export, resuming after interruption, receiving pages out of order, or observing a deletion must
not silently create duplicate candidate revisions or restore stale content. This behavior must be
fixed before a dry-run CLI or durable quarantine is introduced.

The local PoC has no authorized vendor API, company data, database import, credential, or source ACL
evaluator. ENT-C therefore needs a deterministic reference engine whose checkpoint can later be
persisted by an adapter without making persistence part of the reconciliation policy.

## Decision

ENT-C accepts these public contracts:

```text
enterprise-sync-checkpoint.v1
enterprise-sync-result.v1
enterprise-sync-fixture-corpus.v1
```

`EnterpriseSyncCheckpoint` owns the next page index/token, last committed cursor, reconciled source
states, record audit, and retry audit. Checkpoints are returned only after a whole page is applied.
Resume begins at `next_page_index`; a completed checkpoint returns an exact no-op for the same page
set.

```text
EnterpriseSyncMode        = FULL | INCREMENTAL
EnterpriseSyncStatus      = COMPLETED | PAUSED | FAILED
EnterpriseSyncDisposition = APPLIED | NO_CHANGE | QUARANTINED | REJECTED
```

The engine is a pure application function. It does not sleep, write storage, call HTTP, mutate a
canonical Project, or evaluate a real principal. A fixture-supplied failure count simulates page
read failures. `EnterpriseSyncPolicy` fixes the maximum attempts and every deterministic backoff
duration. Exhaustion returns `FAILED` at the same page token, so a caller can resume explicitly.

## Idempotency and reconciliation policy

Stable identity remains the ENT-A tuple. For each identity the checkpoint retains version-to-hash
observations, the current content hash/source version, maximum observed source-update time, deletion
state, mapping revision, and current ENT-B mapping result.

- Repeated identity/version/hash is `NO_CHANGE` and does not increment `mapping_revision`.
- Reused identity/version with a different hash is `QUARANTINED`.
- A different version with unchanged content advances source metadata but not mapping revision.
- An active record older than the maximum reconciled source-update time is `QUARANTINED`.
- An accepted changed record increments the mapping revision exactly once.
- `DELETED` and `RESTRICTED` metadata records apply without payload. A later-arriving stale active
  record cannot restore their prior content.
- ENT-B late-arrival reason codes remain on the sync audit. Business-effective time is not silently
  rewritten to source-update or ingestion time.

Source state is sorted by stable identity. Record audit order follows page and record order. Each
audit ID is a SHA-256 of stable input coordinates and outcome fields, so one-shot and
interrupted/resumed execution produce identical state and audit.

`mapping_revision` counts candidate-state changes inside the ENT-C checkpoint. It is not a domain
Project aggregate version, database revision, or imported Event count.

## Full and incremental semantics

`FULL` and `INCREMENTAL` use the same reconciliation rules. The mode describes orchestration intent;
it does not select a second mapping algorithm. One-shot incremental execution and paused/resumed
incremental execution must produce byte-equivalent validated checkpoints. A full run over the same
ordered pages must produce the same reconciled source states and record audit; only the declared mode
differs.

## Authority and operation boundaries

- ENT-B output remains a candidate; ENT-C `APPLIED` is not human or canonical import approval.
- The checkpoint is serializable state, not a repository or a persistence guarantee.
- Retry scheduling is data only; a later adapter owns clocks, transport, and durable transactions.
- ENT-D owns validation/dry-run commands, canonical diffs, persisted quarantine/resolution, and
  quality reports.
- ENT-E owns synthetic principal/ACL exposure policy and operational health contracts.
- C0 owns real authentication, authorization, company fields, retention, and network decisions.
- No write-back is authorized.

## Rejected alternatives

- Implementing retry with sleep: couples policy tests to wall-clock timing.
- Using only source version for identity: source systems can reuse or conflict on versions.
- Letting a stale active record restore deleted/restricted content: violates fail-closed
  reconciliation.
- Writing directly to Project repositories: bypasses ENT-D review and canonical validation.
- Adding a vendor SDK or database checkpoint now: changes transport and persistence with the policy
  and cannot be validated outside the company environment.

## Verification gate

ENT-C passes only when cursor/page token resume has no missing record, completed replay is an exact
no-op, duplicates do not inflate mapping revision, bounded retry exposes its schedule and failure
page, tombstone/restriction wins over stale active content, late arrival remains explicit,
one-shot/resumed output is deterministic, generated contracts and fixture hashes are current, and
the full non-PostgreSQL regression and repository boundary checks pass.
