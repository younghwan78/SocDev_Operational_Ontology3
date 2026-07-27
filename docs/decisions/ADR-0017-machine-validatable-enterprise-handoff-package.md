# ADR-0017: Machine-validatable enterprise handoff package

- Status: Accepted
- Date: 2026-07-27
- Scope: ENT-F, fixture-only internal discovery handoff

## Context

ENT-A~E define and verify a source-neutral record, mapping candidates, deterministic synchronization,
no-write dry-run, and synthetic security/operation behavior. Those contracts do not by themselves
tell an internal operator which values remain unknown, which checks were already verified outside
the company, or when a read-only pilot must stop.

The home environment cannot discover a company source schema, network path, identity method, ACL,
retention policy, owner, or approved Project. Shipping guessed values would be more dangerous than
leaving them explicit. Shipping a live import command would also bypass the C0/C1 approval boundary.

## Decision

ENT-F accepts four contracts:

```text
enterprise-handoff-mapping-template.v1
enterprise-environment-worksheet.v1
enterprise-pilot-runbook.v1
enterprise-handoff-package.v1
```

The mapping templates cover the vendor-neutral `WORK_TRACKER` and `KNOWLEDGE_BASE` source kinds.
Canonical target fields and statuses are fixed, while every actual source field/status and mapping
version remains the literal `INTERNAL_REQUIRED`.

The environment worksheet requires deployment/version, network/proxy/certificate, identity/access
method, secret-manager reference, ACL/classification, retention/deletion, rate limit, data owner,
security owner, human decision authority, and model-provider policy. Internal items remain null with
`UNCONFIRMED_INTERNAL`. Credential-like values are never a worksheet field; only a reference to an
approved internal secret mechanism may be recorded inside the company.

The pilot template fixes:

```text
max_project_count = 1
read_only = true
write_back_enabled = false
canonical_import_authorized = false
live_use_authorized = false
```

The runbook sequence is immutable:

```text
VALIDATE → DRY_RUN → REVIEW → IMPORT → RECONCILE
```

`VALIDATE`, `DRY_RUN`, and `REVIEW` have executable local commands. `IMPORT` and `RECONCILE` have
`COMPANY_APPROVAL_REQUIRED` authority and deliberately contain no command. They may only be designed
and implemented after internal C0 discovery and C1 approval.

The package manifest pins each artifact by SHA-256 and distinguishes:

- `EXTERNALLY_VERIFIED`: ENT-A~E code/contract evidence with an ADR reference.
- `INTERNAL_REQUIRED`: environment, mapping, one-Project allowlist, and human approval with no
  external evidence claim.

## CLI boundary

```text
soc-ot enterprise validate-handoff
```

The validator loads only the handoff package, verifies the artifact hashes and contracts, and reports
the number of unfilled internal items. It opens no database, network connection, source adapter, or
secret store and writes nothing.

## Consequences

- The repository can be carried into the company with no guessed company configuration.
- A changed worksheet or mapping template invalidates the package hash until explicitly reviewed.
- Expected pilot metrics remain `NOT_EVALUATED`; synthetic success is not presented as an internal
  pilot result.
- An approved internal copy may fill the templates, but real values and exports must stay outside
  this repository and its Git history.
- ENT-F completes external preparation only. Internal C0 discovery is the next gate.

## Rejected alternatives

- Product-specific templates: they would couple the PoC before internal schema discovery.
- Example company IDs, URLs, users, or fields: examples are easy to mistake for approved values.
- A runnable import placeholder: a placeholder command still creates an unsafe execution path.
- One untyped checklist document: prose alone cannot reject drift, filled secrets, write-back, or
  stage reordering.
- Treating ENT-A~E verification as internal readiness: company ACL, retention, ownership, and source
  quality remain unobserved.

## Verification gate

ENT-F passes only when both source kinds and all Project-operation candidate types have templates,
all company values remain unconfirmed/null, the pilot is limited to one Project and read-only,
rollback triggers/actions exist, stage order is fixed, import/reconcile have no command, expected
security/write/reconciliation metrics are zero and `NOT_EVALUATED`, package hashes are current,
external/internal checklist ownership is disjoint, vendor names and company data are absent, the CLI
opens no database, generated contracts are current, and the full repository checks pass.
