# P0/P1 Implementation Readiness 결과

> 원 판정: **READY FOR I0 SCAFFOLD**  
> 현재 상태: **I0–I7 Replay·Codex CLI B2 runtime 및 post-I7 UX-G 복구·검토 문맥 유지 완료**
> 작성일: 2026-07-11  
> 범위: 집에서 synthetic fixture로 구현하는 SoC Operational Decision Twin  
> 주의: 본문은 구현 전 P0/P1 판정 기록이다. 현재 구현 증거는 `docs/implementation/`을 따른다.

## 1. 결론

P0/P1에서 구현 전에 확정해야 할 항목을 모두 닫았다. 이제 기존 프로젝트를 복사하거나 기능을 바로 확장하지 않고, [Master Execution Plan](01_MASTER_EXECUTION_PLAN.md)의 I0부터 새 repository scaffold를 만들 수 있다.

첫 제품은 다음 하나로 고정한다.

```text
사용자: Multimedia System/Architecture Reviewer
업무: Video Recording Scenario 변경 의사결정 검토
첫 case: CASE-VR-001 UHD60 EIS power-gap
데이터: synthetic fixture only
집에서의 최종 결정: simulated Decision Chair
CI 기준: ReplayProvider
선택적 실제 모델 검증: OpenAI Responses API
```

## 2. P0 종료 결과

P0는 잘못 정하면 구조를 다시 뜯어야 하거나 평가의 신뢰성을 훼손하는 항목이다.

|P0 항목|확정 결과|구현 근거|
|---|---|---|
|단일 실행 기준과 repository 구조|`backend/src/soc_ot`, `frontend/src`를 포함한 canonical tree와 I0~I7 순서 확정|[01](01_MASTER_EXECUTION_PLAN.md)|
|DB/Agent worker 선후관계|PostgreSQL과 durable run repository를 I2에서 먼저 구현한 뒤 I4 Agent worker 구현|[01](01_MASTER_EXECUTION_PLAN.md)|
|시뮬레이션 시간과 단위|명시적 명령으로만 전진하는 logical integer step과 canonical unit 확정|[03](03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md)|
|Outcome 표현과 닫힌 선택지|fixture 내 실행식 금지, typed Python `OutcomeRule` registry와 closed-world option 적용|[03](03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md)|
|평가 데이터 분리|development/validation/sealed-unseen 분할, hash manifest, 개봉·폐기 규칙과 한계 확정|[04](04_EVALUATION_PROTOCOL.md)|
|Agent provider/예산/timeout|Replay CI, OpenAI live, call/round/token/cost/timeout/retry 상한 확정|[05](05_AGENT_RUNTIME_AND_SECURITY_POLICY.md)|
|주 사용자와 승인 경계|System/Architecture Reviewer를 primary persona로, 집의 Chair를 simulation으로 제한|[02](02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md)|

P0 미해결 항목: **0개**

## 3. P1 종료 결과

P1은 I0/I1 시작은 가능해도 live Agent와 신뢰 가능한 E2E 이전에 반드시 닫아야 하는 항목이다.

|P1 항목|확정 결과|구현 근거|
|---|---|---|
|Hidden fixture 보안|HTTP hidden endpoint 폐기, authoring-mode CLI와 Outcome/Evaluation port만 허용|[05](05_AGENT_RUNTIME_AND_SECURITY_POLICY.md)|
|Secret와 로그|환경변수/secret store, redaction, raw response 30일, key 영구 미저장|[05](05_AGENT_RUNTIME_AND_SECURITY_POLICY.md)|
|Prompt/provider version|committed prompt bundle hash와 run별 requested/returned model 기록|[05](05_AGENT_RUNTIME_AND_SECURITY_POLICY.md)|
|Schema와 migration|Pydantic → JSON Schema, FastAPI → OpenAPI → TS client, immutable Alembic 정책|[06](06_SCHEMA_CI_AND_CHANGE_POLICY.md)|
|CI 실행 기준|Backend/Frontend/contract/hidden/secret/E2E 명령과 job 순서 확정|[06](06_SCHEMA_CI_AND_CHANGE_POLICY.md)|
|한국어 UI text 제약|machine code와 번역 분리, action/navigation/header 길이와 오류문 원칙 확정|[06](06_SCHEMA_CI_AND_CHANGE_POLICY.md)|
|Windows 로컬 실행|port, env, setup, API/worker/UI, replay/live, smoke, stop, 장애 대응 확정|[07](07_LOCAL_DEVELOPMENT_RUNBOOK.md)|
|평가 합격 기준|결정론적 validator 우선, process/outcome 분리, ablation과 명시적 live 안정성 범위 확정|[04](04_EVALUATION_PROTOCOL.md)|
|상태·API·시간·version 용어|네 상태 공간, uppercase DecisionType, canonical API와 version vocabulary 확정|[08](08_CANONICAL_TERMS_AND_API_CONTRACT.md)|

P1 미해결 항목: **0개**

## 4. 문서 패키지 읽는 순서

1. 이 문서 — 무엇이 닫혔고 구현을 시작해도 되는지 확인
2. [01_MASTER_EXECUTION_PLAN.md](01_MASTER_EXECUTION_PLAN.md) — 폴더, 기술, I0~I7 순서와 gate
3. [02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md](02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md) — 누구를 위한 제품이고 누가 무엇을 승인하는지
4. [03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md](03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md) — 시간, 측정, 개발 사건, Outcome 규칙
5. [04_EVALUATION_PROTOCOL.md](04_EVALUATION_PROTOCOL.md) — case 분할, 합격선, sealed-unseen 운영과 ablation
6. [05_AGENT_RUNTIME_AND_SECURITY_POLICY.md](05_AGENT_RUNTIME_AND_SECURITY_POLICY.md) — Agent 실행, provider, 비용, 보안
7. [06_SCHEMA_CI_AND_CHANGE_POLICY.md](06_SCHEMA_CI_AND_CHANGE_POLICY.md) — contract 생성, migration, CI, 변경 절차
8. [07_LOCAL_DEVELOPMENT_RUNBOOK.md](07_LOCAL_DEVELOPMENT_RUNBOOK.md) — Windows에서 실제로 실행할 명령과 port
9. [08_CANONICAL_TERMS_AND_API_CONTRACT.md](08_CANONICAL_TERMS_AND_API_CONTRACT.md) — 상태, decision type, API, logical time, version 이름

## 5. 구현 시작 체크리스트

- [x] 첫 사용자, workflow, case가 하나로 고정됨
- [x] 회사 connector와 synthetic fixture 경계가 명확함
- [x] 기존 `E:\56_Codex_SoC_Operational_Ontology`를 자동 복사하지 않음
- [x] canonical repository tree와 단계별 gate가 하나임
- [x] PostgreSQL이 durable Agent worker보다 먼저임
- [x] observable/hidden 의존성 경계가 테스트 가능함
- [x] 불완전한 측정을 exact/range/qualitative/unknown으로 표현 가능함
- [x] 저후회 결정의 guardrail/trigger/rollback이 실행 가능한 contract임
- [x] ReplayProvider만으로 CI와 E2E가 가능함
- [x] live provider의 상한, retry, failure, 비용 정책이 있음
- [x] schema/API/Frontend type/migration 변경 경로가 있음
- [x] validation/sealed-unseen 오염을 방지하고 로컬 일반화 주장을 제한하는 규칙이 있음
- [x] Role Agent가 baseline보다 낫지 않으면 단순화하는 ablation과 stop rule이 있음
- [x] 한국어 중심 UI의 사용자와 정보 우선순위가 있음
- [x] Windows 로컬 port와 명령이 서로 충돌하지 않음

## 6. I0에서 실제로 생성할 것

다음 작업부터가 제품 구현의 시작이다.

```text
1. canonical folder와 Git repository
2. pyproject.toml, uv.lock, Backend package와 empty tests
3. React/TypeScript/Vite package와 empty tests
4. PostgreSQL-only Docker Compose
5. .env.example과 secret-safe .gitignore
6. lint, typecheck, unit test, build 명령
7. contract/hidden/secret/markdown/plan-consistency 검사 script
8. AGENTS.md와 root README
```

I0 완료 판정:

- API key 없이 Backend/Frontend 기본 test가 통과한다.
- PostgreSQL health check가 통과한다.
- 문서의 canonical 경로 외 중복 source tree가 없다.
- plan-consistency 검사가 상태, case 수, enum, API와 version vocabulary의 drift를 탐지한다.
- [07_LOCAL_DEVELOPMENT_RUNBOOK.md](07_LOCAL_DEVELOPMENT_RUNBOOK.md)의 I0 해당 명령이 실제로 실행된다.

## 7. 남은 비차단 외부 조건

|조건|영향|현재 대응|
|---|---|---|
|OpenAI API key와 model access|I7 live 안정성 평가에 필요|I0~I7 Replay는 완료했으며 live 호출 전 예산 차단을 유지|
|사내 Confluence/Jira schema와 인증|사내 pilot에서 필요|집에서는 connector를 구현하지 않고 fixture import port만 유지|
|실제 사내 human approval policy|사내 운영 전 필요|집의 Chair 결과에는 `simulated` 표시를 강제|

이 조건들은 완료된 Replay 구현을 소급해 막지 않지만 I7 Live 통과를 주장할 수 없게 한다.

## 8. 기존 문서와 충돌 시 처리

이 문서는 상태판이며 제품·기술 규범을 소유하지 않는다. `PROJECT_PLAN.md`는 제품 범위, `01_MASTER_EXECUTION_PLAN.md`는 I0~I7 실행, `02~08`은 각 분야 contract를 소유한다. `docs/PLAN_INDEX.md`에서 변경 영역의 owning document를 먼저 확인한다. Supporting internal docs의 다른 폴더 구조, API synonym, DB보다 빠른 worker 단계와 hidden HTTP endpoint는 폐기된 제안이다.

## 9. 최종 판단

**P0/P1 설계 결정은 완료되었고 그 판정에 따라 I0–I7 Replay 구현과 gate 검증까지 완료했다.** 외부 key·가격·비용 승인에 의존하는 I7 Responses API gate는 실행하지 않았다. 별도 post-I7 UX roadmap은 UX-A부터 UX-G 복구·검토 문맥 유지까지 완료했다. UX-F/UX-G 결과는 agent-substitute 공학 검증이며 실제 사람의 이해도, 의사결정 속도나 business value를 증명하지 않는다. 다음 UX-H는 공정한 baseline fixture와 human participant가 필요하며, 사내 연동과 실제 업무 적용은 여전히 별도 C0 승인 범위다.
