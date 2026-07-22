# 전체 계획 문서 안내

> 상태: Active  
> 갱신일: 2026-07-23
> 현재 단계: OPS-F study release/rubric/E2E 도구 구현 완료, 독립 관측 baseline 0/5·product 0/5로 Gate 진행 중; UX-I 차단

> 고정 후속 순서: OPS-F 관측 → UX-I/J/K Local UX Release 1 → ENT-A~F 사외 준비 → 사내 C0/C1

이 문서는 제품 계획부터 구현 계약까지 어떤 문서를 어떤 순서로 읽고 수정해야 하는지 안내한다. 문서 간 충돌은 전체 순위가 아니라 각 문서가 소유한 결정 영역으로 해결한다.

## 1. 처음 읽을 문서

|순서|문서|읽고 답할 질문|
|---:|---|---|
|1|`PROJECT_PLAN.md`|왜 만들며 무엇을 검증하고 언제 축소·중단하는가|
|2|`docs/readiness/00_IMPLEMENTATION_READINESS_RESULT.md`|현재 구현을 시작해도 되는가|
|3|`docs/readiness/01_MASTER_EXECUTION_PLAN.md`|어떤 폴더와 I0~I7 순서로 구현하는가|
|4|`docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md`|상태, enum, API, 시간과 version 이름은 무엇인가|
|5|현재 I 단계가 참조하는 분야별 readiness 문서|어떤 contract와 gate를 구현하는가|

## 2. 문서별 소유권

|문서|소유하는 결정|소유하지 않는 결정|
|---|---|---|
|`PROJECT_PLAN.md`|제품 목표, scope, persona, 가치 가설, kill criterion, 회사 전환|폴더, endpoint 세부, 실행 명령|
|`00_IMPLEMENTATION_READINESS_RESULT.md`|P0/P1 상태, 현재 단계, 차단 조건|제품·기술 규범|
|`01_MASTER_EXECUTION_PLAN.md`|repository, 기술 기준, I0~I7 순서와 stage gate|제품 가치 가설의 변경|
|`02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md`|persona, Lab/Company 승인과 usability task|Frontend component 구현|
|`03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md`|logical step, quantity, measurement, OutcomeRule|API route와 UI 상태|
|`04_EVALUATION_PROTOCOL.md`|corpus, freeze, ablation, evaluator, 합격선|Agent provider 구현|
|`05_AGENT_RUNTIME_AND_SECURITY_POLICY.md`|provider, call/token/cost, retry, hidden, secret|domain state와 outcome truth|
|`06_SCHEMA_CI_AND_CHANGE_POLICY.md`|schema source, versioning, migration, CI, 변경 절차|제품 scope|
|`07_LOCAL_DEVELOPMENT_RUNBOOK.md`|Windows port, environment, 실행·검증 명령|아직 구현되지 않은 기능의 현재 상태 주장|
|`08_CANONICAL_TERMS_AND_API_CONTRACT.md`|enum, 상태 공간, endpoint, command, version vocabulary|화면 layout과 DB physical schema|

## 3. Supporting design

다음 문서는 구현 배경과 상세 설계 예시를 제공한다. Canonical contract를 변경하지 않는다.

- `internal_docs/26.07.11 Role Agent 기반 단계별 구현 계획.md`
- `internal_docs/26.07.11 Backend Frontend 및 UX 기술 설계.md`
- `internal_docs/26.07.16 결정 중심 UX 설계.md`
- `internal_docs/26.07.17 UX-A Development Twin 계약 및 Content Fixture 구현 보고서.md`
- `internal_docs/26.07.17 UX-B Decision Inbox 구현 및 검증 보고서.md`
- `internal_docs/26.07.17 UX-C Decision Brief 및 Development Twin 구현 보고서.md`
- `internal_docs/26.07.17 UX-D 선택지 이견 및 불확실성 구현 보고서.md`
- `internal_docs/26.07.17 UX-E 안전 조건 행동 및 결과 구현 보고서.md`
- `internal_docs/26.07.17 UX-F Responsive 접근성 및 사용성 Gate 보고서.md`
- `internal_docs/26.07.19 UX-G 복구 및 검토 문맥 유지 구현 보고서.md`
- `internal_docs/26.07.19 UX-H Human baseline 및 측정 계약 구현 보고서.md`
- `internal_docs/26.07.21 OPS-A Project Operations Scope 및 Fixture 전환 계획.md`
- `internal_docs/26.07.21 OPS-B Project 중심 Fixture 구현 및 검증 보고서.md`
- `internal_docs/26.07.21 OPS-C Project Runtime Projection API 구현 및 검증 보고서.md`
- `internal_docs/26.07.22 OPS-D Project Portfolio Situation UX 구현 및 검증 보고서.md`
- `internal_docs/26.07.22 OPS-E Risk Detail Decision Linkage 구현 및 검증 보고서.md`
- `internal_docs/26.07.22 OPS-F Project 중심 사용성 Protocol v2 구현 및 검증 보고서.md`
- `internal_docs/26.07.23 OPS-F Study Release 보강 및 사내 데이터 연결 준비도 보고서.md`
- `internal_docs/26.07.23 UX 마무리 및 사내 데이터 전환 실행 계획.md`
- `docs/decisions/ADR-0010-project-operations-and-risk-provenance.md`

다음 문서는 과거 판단의 근거다. 새 구현 기준으로 직접 사용하지 않는다.

- `docs/ADDITIONAL_REQUIREMENTS_REVIEW.md`
- `docs/OLD_PROJECT_ASSET_REVIEW.md`
- `internal_docs/26.06.18 SoC ontology (ChatGPT).md`
- `internal_docs/26.07.05 비지니스 가치 논의.md`

## 4. 변경할 때 확인할 문서

|변경|함께 갱신할 문서|
|---|---|
|제품 목표, persona, 첫 workflow|`PROJECT_PLAN`, `02`, `00`|
|I 단계, repository, 기술 선택|`01`, `00`, `07`|
|상태, decision type, API, version 이름|`08`, `06`, technical design, `07`|
|Agent topology와 budget|`05`, `04`, `01`|
|Fixture 수, partition, freeze|`04`, `01`, `PROJECT_PLAN`, Role design|
|Outcome 시간·rule|`03`, `08`, `04`|
|UI 질문·primary action|`02`, technical design, E2E test|

모든 변경은 `docs/readiness/06_SCHEMA_CI_AND_CHANGE_POLICY.md`의 checklist를 따른다.

## 5. 현재 실행 지점

I0~I7 Replay와 post-I7 UX-A/UX-B/UX-C/UX-D/UX-E/UX-F/UX-G 로컬 Gate,
OPS-F Project protocol v2와 study release/rubric/E2E 도구까지 구현됐다. 현재 실행 지점은 OPS-F 독립 관측 수집이며 UX-I는 차단 상태다.
UX-I/J/K로 Local UX Release 1을 먼저 닫은 뒤 ENT-A~F의 fixture-only enterprise preparation을
진행하고, 그 결과를 가지고 사내 C0/C1에 들어간다. UX와 connector는 동시에 변경하지 않는다.

```text
UX-F Responsive·접근성·사용성 Gate
  → 390px, 768px, desktop과 200% zoom 등가 reflow PASS
  → keyboard와 screen reader semantics PASS
  → partial, stale, conflict E2E PASS
  → frozen CASE-VR-001 canonical 8 + Development Twin 5 질문 PASS
UX-G 복구·검토 문맥 유지
  → raw network 오류 비노출과 한국어 recovery action PASS
  → at_step + 모바일 선택지 URL reload/Back/Forward PASS
  → canonical action 유지, 설명용 한국어와 interaction state 보강
UX-H Human baseline·측정 계약
  → observable hash-pinned Jira/Confluence형 baseline fixture PASS
  → frozen 13-task protocol + session/event/summary schema PASS
  → builder dry-run은 not_ready/no_business_claim, 실제 human 결과는 0건
OPS-A Project Operations Scope/ADR
  → Project/Issue/Risk/Gate 의미와 provenance 경계 확정
  → world.yaml의 event 항목은 UX fixture 다양성에 도움이 되는 경우만 선택 참조
  → OPS-B~OPS-F 순서와 stage Gate 확정, human session은 OPS-F까지 보류
OPS-B Project 중심 Fixture
  → PROJECT-U/V/W의 lifecycle·evidence·commitment posture 분리
  → 17개 typed event와 Issue→Risk→Milestone/Decision provenance 검증
  → historical future-leakage, cross-project lineage와 immutable hash PASS
OPS-C Project Runtime·Projection·API
  → PostgreSQL 0020 + in-memory/PostgreSQL parity와 restart persistence PASS
  → ProjectAttention/RiskLevel·ordering reason/source deterministic policy PASS
  → Portfolio/Situation/Risk/Timeline 5개 read API와 동일 at_step boundary PASS
OPS-D Project Portfolio·Situation UX
  → Backend 정렬과 reason을 보존한 `/projects` 기본 진입 PASS
  → top Risk → source Issue/Evidence/Event → 영향 WorkItem/Milestone progressive disclosure PASS
  → URL `at_step`, fail-closed recovery, 390px/desktop·Axe·overflow local proxy PASS
OPS-E Risk Detail·Decision linkage
  → source → epistemic/inference → 영향 → Decision/Action 단일 추적 경로 PASS
  → Project 역사 시점과 Decision 시점을 섞지 않는 왕복 URL 문맥 PASS
  → 390px/desktop, Axe, overflow, console 및 기존 Decision E2E 회귀 PASS
OPS-F Project 중심 protocol v2
  → PROJECT-U/V/W hash-pinned baseline 6개 surface + 고정 task 11개 PASS
  → baseline/product 동일 task guide, 제품 release hash와 reviewer-only rubric PASS
  → draft/excluded attrition 보고와 Project current/historical E2E PASS
  → 완료 독립 관측 baseline 0/5·product 0/5, not_ready/no_business_claim
UX-I/J/K Local UX Release 1
  → OPS-F 상위 문제만 축소·개선
  → human initial response와 Agent advice 이후 accept/modify/reject 분리
  → 전체 Project→Decision→Outcome 여정과 복구·접근성·역사 경계 재동결
ENT-A~F 사외 준비
  → source-neutral ingestion + dirty fixture mapping + idempotent sync
  → dry-run/quarantine + ACL/classification emulator + 사내 handoff kit
  → 실제 company data, vendor API, credential, auth와 write-back 없음
```

UX-F/UX-G 완료는 local Codex evaluator와 deterministic browser automation의 공학적 Gate다.
실제 사용자 시간, 의사결정 속도, 조언 품질, 승인이나 사내 연동 완료를 의미하지 않는다.
UX-H는 공정한 비교 fixture와 측정 도구가 준비됐다는 뜻이며 human usability 또는 business
value 결과가 아니다. 새 Project Operations 정보 구조를 반영한 OPS-F protocol v2는 준비됐지만,
condition별 proxy/domain reviewer 5개 이상을 기록하기 전에는 UX-I와 business claim을 시작하지
않는다. C0와 I7 Responses API gate는 필요한 사용자·회사
입력과 key·가격·비용 승인 전에는 시작하지 않는다.
