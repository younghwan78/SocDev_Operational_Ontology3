# 전체 계획 문서 안내

> 상태: Active  
> 갱신일: 2026-07-11  
> 현재 단계: I0–I7 Replay 완료, I7 Live gate 외부 입력 대기

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

현재 승인된 다음 작업은 I0뿐이다.

```text
I0 Repository and quality scaffold
  → canonical folder
  → root Python package and Frontend package
  → PostgreSQL Compose
  → no-key test commands
  → consistency/security check scripts
```

CASE-VR-001 domain 구현, Agent prompt, UI 기능과 과거 코드 port는 I0 gate를 통과하기 전에 시작하지 않는다.
