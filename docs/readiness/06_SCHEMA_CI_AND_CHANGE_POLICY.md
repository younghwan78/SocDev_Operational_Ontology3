# Schema, CI, and change policy

> Status: APPROVED  
> Date: 2026-07-11

## 1. Purpose

This document prevents drift between Python domain contracts, fixture YAML, HTTP APIs, PostgreSQL migrations, and Frontend types.

## 2. Contract source of truth

|Artifact|Source|Generated consumer artifact|
|---|---|---|
|Domain/command/result data|Pydantic v2 models|JSON Schema in `contracts/generated/`|
|Canonical state, enum, API, version vocabulary|`08_CANONICAL_TERMS_AND_API_CONTRACT.md`|Pydantic/OpenAPI/TypeScript reuse|
|HTTP contract|FastAPI route and response models|OpenAPI JSON|
|Frontend API types|committed OpenAPI snapshot|generated TypeScript client|
|Database structure|SQLAlchemy mapping plus Alembic revision|PostgreSQL schema|
|Fixture vocabulary|typed enums and dictionary fixtures|Korean UI label map|

Generated files are committed for review but never hand-edited.

## 3. Contract identity and compatibility

Use stable names such as `role-review.v1` and `decision-dossier.v1`. Use the version field names defined in `08_CANONICAL_TERMS_AND_API_CONTRACT.md`; do not overload `case_version`.

|Change|Rule|
|---|---|
|Add optional field with defined default|compatible within major version|
|Add enum value|compatible only when every consumer has explicit unknown handling|
|Add required field|new major version|
|Remove or rename field|new major version|
|Change field meaning, unit, or cardinality|new major version|
|Tighten validation so an accepted file becomes invalid|new major version or migration|

Readers reject unknown major versions. They may accept newer compatible minor metadata only when configured.

## 4. Fixture versioning

Every fixture declares:

```yaml
schema_version: observable-case.v1
fixture_version: 1
dictionary_version: soc-dictionary.v1
outcome_rule_version: outcome-rules.v1
```

Evaluation manifests pin fixture SHA-256 hashes. Imported fixtures store both source hash and contract version. Editing a case creates a new `fixture_version`; it does not mutate a completed evaluation record.

## 5. Database migrations

- Alembic revisions are immutable after they reach the shared main branch.
- Every persistent-model change includes an upgrade migration and rollback/restore note.
- Destructive or lossy migration requires backup, explicit approval, and a data migration test.
- Application startup checks the database revision and refuses normal operation when incompatible.
- I2 repository parity tests run against both in-memory and PostgreSQL adapters.

## 6. Prompt and policy changes

Prompt bundle, routing policy, decision policy, and OutcomeRule registry have independent versions. Any change affecting Agent or outcome behavior requires:

- reason and expected effect
- changed version identifier
- development regression result
- validation result
- a new sealed-unseen release if prior sealed details informed the change

## 7. Required CI commands

Backend:

```powershell
uv sync --all-groups
uv run ruff check backend/src backend/tests
uv run mypy backend/src
uv run pytest -m "not postgres" -p no:cacheprovider
uv run pytest -m postgres -p no:cacheprovider
uv run python -m soc_ot.cli contracts export --check
uv run alembic upgrade head
```

Frontend:

```powershell
Set-Location frontend
npm ci
npm run typecheck
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```

Repository checks:

```powershell
powershell -File scripts/check-generated-contracts.ps1
powershell -File scripts/check-hidden-boundary.ps1
powershell -File scripts/check-secrets.ps1
powershell -File scripts/check-markdown-links.ps1
powershell -File scripts/check-plan-consistency.ps1
```

These commands are the implementation contract. I0 must add the scripts and package entries before claiming the scaffold gate.

`check-plan-consistency` verifies at least the active document status, I0~I7 ordering, 8-case corpus, canonical `DecisionType`, `/api/v1/decision-cases`, `/api/v1/runs`, forbidden hidden HTTP route, and version vocabulary.

CI starts a PostgreSQL service and waits for its health check before migration or `-m postgres` tests. Migration CI checks both an empty-database upgrade and an upgrade from the oldest supported revision. Unit tests do not require PostgreSQL.

Frontend E2E uses Playwright `webServer` or a repository orchestration script to start the API, worker, Vite, import a frozen fixture, and stop all processes. A bare `npm run test:e2e` must not assume manually running services.

## 8. CI job order

```text
static checks
  -> contract generation drift
  -> unit tests
  -> PostgreSQL health, migration, and integration tests
  -> Frontend tests/build
  -> ReplayProvider E2E
  -> fixture/evaluation validation
  -> secret and hidden-boundary checks
```

Live OpenAI calls do not run in ordinary pull-request CI.

I0 selects cross-platform Python/Node commands for ordinary CI. PowerShell scripts remain Windows local wrappers and call the same underlying checks.

## 9. Change checklist

For any model, API, fixture, prompt, rule, or database change:

- [ ] identify source-of-truth artifact
- [ ] update `08_CANONICAL_TERMS_AND_API_CONTRACT.md` first when changing state, enum, endpoint, time, or version vocabulary
- [ ] classify compatibility and version impact
- [ ] update generated schema/OpenAPI/TypeScript artifacts
- [ ] add or update migration where persistent data changes
- [ ] update fixture and manifest hashes
- [ ] add positive, negative, and backward-compatibility tests
- [ ] update Korean label/help text where user-visible
- [ ] record decision or migration note under `docs/decisions/`
- [ ] run all applicable CI commands

## 10. Korean UI text constraints

- Enum values remain stable English machine codes; Korean labels are presentation data.
- Primary action label target: 12 Korean characters or fewer.
- Navigation label target: 10 Korean characters or fewer.
- Table header target: 12 Korean characters or fewer; provide tooltip for necessary technical terms.
- Error messages state what failed, impact, and next action in Korean.
- Do not encode business logic by comparing translated strings.

## 11. Definition of Done

A change is done only when:

- code, contracts, migration, fixtures, and generated consumers agree
- tests pass in ReplayProvider mode without an API key
- no hidden data or secret crosses its boundary
- failure and empty states are handled
- audit/version metadata can reproduce the decision input
- relevant readiness gate and documentation are updated

## 12. Decision records

Create an ADR before changing a fixed master-plan choice, importing code from the old project, adding a graph/vector database, allowing Agent tools, or changing the home approval boundary. ADR acceptance updates the readiness result and affected contracts together.
