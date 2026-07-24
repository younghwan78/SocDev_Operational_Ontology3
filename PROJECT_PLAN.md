# SoC 개발 의사결정 디지털 트윈을 어떻게 구현하고 검증할 것인가

> 문서 상태: Product Plan v0.3, 로컬 PoC 구현 승인
> 갱신일: 2026-07-25
> 문서 역할: 제품 목표, 범위, 가치 가설, 중단 기준을 정의  
> 현재 판단: **GO: I0–I7 Replay, Step 5 B2 runtime, UX-A~UX-K와 ENT-A~C 구현 완료**, **DEFERRED: OPS-F human observation baseline 0/5·product 0/5**, **NEXT: ENT-D**, **NO-GO: human UX·business value 주장, live 사내 연동 및 실제 업무 적용**

후속 실행 순서는 `OPS-F human observation 보류 → UX-I 완료 → UX-J → UX-K Local UX Release 1 → ENT-A~F
사외 준비 → 사내 C0/C1`로 고정한다. UX와 connector를 동시에 변경하지 않는다.

이 계획은 SoC 개발 진행과 불확실성을 재현하고 제한된 정보에서도 저후회 결정을 돕는 제품을 정의한다. 집에서는 synthetic fixture로 의사결정 메커니즘만 검증하며, 실제 비즈니스 가치는 사내 read-only 파일럿에서 별도로 측정한다.

## 1. 이 문서가 결정하는 것

`PROJECT_PLAN.md`는 제품의 `왜`와 `무엇`만 결정한다. 구현 폴더, 기술 순서, API, 상태 코드와 실행 명령은 분야별 canonical 문서가 결정한다.

|결정 영역|Canonical 문서|
|---|---|
|제품 목표, 범위, 가치 가설, 중단 기준|`PROJECT_PLAN.md`|
|현재 P0/P1 종료 상태와 다음 단계|`docs/readiness/00_IMPLEMENTATION_READINESS_RESULT.md`|
|Repository와 I0~I7 구현 순서|`docs/readiness/01_MASTER_EXECUTION_PLAN.md`|
|Persona와 승인 경계|`docs/readiness/02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md`|
|시뮬레이션, 측정, Outcome 규칙|`docs/readiness/03_SIMULATION_MEASUREMENT_OUTCOME_CONTRACT.md`|
|평가 corpus, 합격선, ablation|`docs/readiness/04_EVALUATION_PROTOCOL.md`|
|Agent 실행, 비용, 보안|`docs/readiness/05_AGENT_RUNTIME_AND_SECURITY_POLICY.md`|
|Schema, migration, CI, 변경 절차|`docs/readiness/06_SCHEMA_CI_AND_CHANGE_POLICY.md`|
|Windows 로컬 실행|`docs/readiness/07_LOCAL_DEVELOPMENT_RUNBOOK.md`|
|상태, enum, API, 시간 용어|`docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md`|

`internal_docs`의 Role Agent 계획과 Backend/Frontend 기술 설계는 상세 설계 참고 자료다. 세부 내용이 위 canonical 문서와 충돌하면 해당 결정 영역의 canonical 문서를 적용한다.

용어는 다음처럼 구분한다.

- `P0/P1`: 구현 전 발견사항의 우선순위
- `I0~I7`: 로컬 PoC의 유일한 구현 단계
- `C0~C2`: 사내 전환 단계
- 과거 `Phase`, `Step`, `Tech Step`: 역사적 crosswalk 외에는 실행 순서로 사용하지 않음

## 2. 제품 결정

### 2.1 한 문장 목표

> **SoC 개발의 진행 상태와 불확실성을 운영 온톨로지로 재현하고, 데이터가 부족해도 가역성, 영향, 일정, 탐지·복구 가능성, 완화책을 고려한 저후회 결정을 조언한다.**

이 제품은 데이터 검색 시스템이나 범용 대화형 AI가 아니다. 사용자가 결정해야 하는 순간에 현재 상황, 선택지, 불확실성, 반대 의견, 안전 조건과 다음 행동을 하나의 검토 흐름으로 제공한다.

### 2.2 첫 결정 계약

첫 vertical slice는 하나의 질문으로 고정한다.

```text
Case:
  CASE-VR-001 UHD60 EIS power-gap

Primary actor:
  Multimedia System/Architecture Reviewer

Trigger:
  Architecture freeze 전에 UHD60 + EIS 기능 방향을 정해야 함

Decision question:
  측정이 완성되지 않은 상태에서 EIS를 제한 조건으로 진행할지,
  가역 시험만 수행할지, 최소 근거가 준비될 때까지 연기할지 결정한다.

Deadline:
  M2 Architecture Freeze

Completion:
  선택, 가정, 반대 의견, guardrail, rollback trigger, owner,
  verification plan, residual risk가 기록됨
```

첫 case는 제품의 장기 범위를 대표하지 않는다. 개발 상태부터 결정, 행동, 시뮬레이션 결과, 평가까지 폐루프가 실제로 연결되는지를 검증한다.

### 2.3 사용자 우선순위

|우선순위|역할|제품에서 하는 일|
|---|---|---|
|Primary|Multimedia System/Architecture Reviewer|상황을 이해하고 선택지·조건·잔여 위험을 검토|
|Secondary|Technical PM/Reviewer|기한, blocker, owner, milestone 영향과 escalation 확인|
|Contributor|HW, SW, Verification, Product 관점|fixture와 Role Agent가 제공하는 전문 검토 관점|
|Developer|Fixture/Agent Developer|case 작성, contract 검사, 평가 실행|

UI와 성공 기준은 Primary persona에 맞춘다. 역할별 dashboard나 독립 제품은 MVP에 포함하지 않는다.

## 3. 해결하려는 문제와 가치 가설

### 3.1 문제 정의

SoC 개발의 판단 지연은 데이터가 없어서만 발생하지 않는다. 개발 track, dependency, 변경 가능 시점, 가정, 반대 근거와 결정 책임이 서로 다른 문서와 대화에 흩어져 있기 때문이다.

현재 방식의 핵심 실패는 다음과 같다.

- Architecture, HW, SW, Verification의 실제 진행 상태를 한 시점 기준으로 재구성하기 어렵다
- evidence 부족과 decision 불가능을 같은 의미로 처리한다
- workaround, option 보존, rollback 조건이 decision record와 분리된다
- 역할별 의견은 남지만 어느 선택과 행동으로 이어졌는지 추적하기 어렵다
- 결정 당시 알 수 있었던 정보와 사후 결과가 섞여 hindsight bias가 생긴다

### 3.2 North Star

> **Situation-to-Decision Time을 줄이면서 critical impact 누락과 통제 없는 진행을 늘리지 않는다.**

속도만 줄이면 성공이 아니다. 시스템은 더 빠른 결정과 함께 근거 추적성, 불확실성 표시, 안전 조건과 철회 가능성을 유지해야 한다.

### 3.3 로컬에서 검증할 제품 가설

|가설|검증 방법|실패 시 대응|
|---|---|---|
|H1. 운영 온톨로지가 현재 개발 상태를 더 명확하게 재구성한다|CASE-VR-001에서 track, blocker, dependency, deadline 정답 rubric 측정|모델을 진행 spine 중심으로 축소|
|H2. 데이터 부족에서도 저후회 선택을 구분한다|가역·비가역·충돌 evidence case의 decision family와 safeguard 검사|조언 범위를 rule-based posture로 제한|
|H3. 전문 Role Agent가 deterministic baseline보다 유효한 관점을 추가한다|deterministic, single-role, routed multi-role, Challenger 포함 구성의 ablation|유의미한 향상이 없으면 single-agent 또는 deterministic 구조로 축소|
|H4. 한국어 Decision Workspace가 raw ontology 없이 판단을 설명하게 한다|정해진 usability task와 정답 rubric 실행|화면과 projection을 단순화|

Role Agent는 제품 철학 때문에 반드시 유지하는 구성요소가 아니다. 검증 결과가 가치를 입증하지 못하면 topology를 줄인다.

### 3.4 로컬에서 증명할 수 없는 것

Synthetic fixture는 다음을 증명하지 못한다.

- 실제 의사결정 시간 단축
- 사내 데이터에서의 영향 분석 정확도
- 현업 전문가의 조언 수용성
- 조직 차원의 품질 또는 일정 개선
- 다른 SoC domain으로의 일반화

로컬 결과는 메커니즘 검증과 사내 파일럿 준비 근거로만 사용한다.

## 4. 제품 범위

### 4.1 로컬 PoC 포함 범위

- Android Mobile SoC의 Multimedia/Video Recording vertical slice
- synthetic fixture 8개: development 3개, validation 2개, sealed unseen 3개
- Architecture, HW, SW, Verification, Measurement의 비동기 진행
- WorkItem, dependency, milestone, decision window와 resource constraint
- Evidence, assumption, unknown과 미래에 공개되는 measurement
- deterministic impact/dependency/deadline/eligibility 분석
- 선택적으로 실행하는 Role Agent, Router, Challenger와 simulated Chair
- deterministic Outcome Engine과 Process/Outcome 분리 평가
- 한국어 Decision Workspace와 개발자용 fixture/evaluation 화면
- ReplayProvider 기반 재현 가능한 CI와 선택적 live-provider 평가

### 4.2 로컬 PoC 제외 범위

- 회사 원문, identifier, KPI, log 또는 실제 과제 정보
- Jira/Confluence connector, 인증, ACL 상속과 write-back
- 물리 성능 simulator, 정확한 PPA estimator, RTL/log/waveform 분석
- 범용 지식 검색 챗봇, portfolio dashboard, risk heatmap
- 자동 승인, 실제 업무 action, 무인 ticket/page 생성
- Graph DB, 별도 vector DB, 범용 agent framework
- Video Recording 밖의 scenario 확장
- 12~20개 이상 case 확대

### 4.3 Lab mode와 company mode

|구분|Lab mode|Company mode|
|---|---|---|
|데이터|synthetic fixture|승인된 사내 source|
|최종 판단|simulated Chair|이름이 기록된 human authority|
|결과|deterministic simulated outcome|실제 action과 관측 outcome|
|목적|기술·의사결정 메커니즘 검증|비즈니스 가치와 업무 적합성 검증|
|허용 주장|local fixture에서 contract/gate 통과|승인된 pilot 범위의 측정 결과|

Company mode에서는 Chair 출력을 recommendation으로만 사용한다. 사용자가 outcome을 수동으로 진행하는 simulation control은 일반 업무 화면에서 제거한다.

## 5. Decision Twin 모델

### 5.1 네 개의 최소 spine

MVP는 객체 수가 아니라 첫 질문을 답하는 네 개의 연결 축으로 모델링한다.

```text
Development spine
  Project → DevelopmentTrack → WorkItem → Dependency → Milestone

Knowledge spine
  Evidence → Claim → Assumption/Uncertainty → Source reference

Decision spine
  DecisionCase → Alternative → Decision → Guardrail/Trigger → Action

Outcome spine
  DevelopmentEvent → Measurement reveal → Outcome → Evaluation
```

새 객체는 다음 조건 중 하나를 만족할 때만 독립 lifecycle로 승격한다.

- 첫 사용자 질문에 새 답을 제공한다
- 독립적인 상태 전이, owner, version 또는 권한 경계가 필요하다
- 기존 객체의 필드로 표현하면 검증 규칙이 모호해진다

조건을 만족하지 않으면 typed attribute 또는 relation으로 유지한다.

### 5.2 Digital Twin 최소 조건

이 프로젝트의 Digital Twin은 RTL 또는 실리콘의 물리 동작을 복제하지 않는다. 특정 의사결정 시점에 개발 상태와 당시 이용 가능했던 지식을 재구성하는 Decision Operations Twin이다.

최소 조건은 다음과 같다.

- 여러 development track이 서로 다른 상태를 가진다
- dependency와 decision deadline이 다음 행동을 제한한다
- 사실, 추론, 가정, 미확인 상태를 구분한다
- 결정 당시 이용 가능했던 evidence만 Role Agent와 Chair에 제공한다
- 선택, guardrail, action이 이후 상태와 outcome을 바꾼다
- process quality와 outcome quality를 별도로 평가한다
- 동일한 frozen input과 simulation step은 동일한 결과를 만든다

### 5.3 시간 의미

로컬 fixture의 domain truth는 logical `simulation_step`이다.

|필드|의미|
|---|---|
|`effective_at_step`|개발 세계에서 사실이 된 step|
|`observed_at_step`|조직이 그 사실을 알게 된 step|
|`available_at_step`|Agent 입력에 포함할 수 있는 step|
|`expires_at_step`|가정·waiver를 재검토해야 하는 step|
|`recorded_at`|감사 목적의 실제 wall-clock 시각|

사내 source의 `valid_time`과 `observed_time`은 C0에서 별도 enterprise 계약으로 정의한다. 로컬 simulation field와 암묵적으로 변환하지 않는다.

### 5.4 상태와 결정 유형

Case lifecycle, Agent run, UI phase와 최종 decision type은 다른 상태 공간이다. Canonical enum과 API는 `docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md`를 따른다.

```text
DecisionCaseStatus:
  DRAFT → CONTEXT_BUILDING → OPTIONS_READY → DECISION_REQUIRED
  → DECIDED → ACTIONING → VERIFIED → CLOSED

DecisionType:
  APPROVE
  APPROVE_WITH_GUARDRAILS
  RUN_REVERSIBLE_TRIAL
  COLLECT_MINIMUM_EVIDENCE
  DEFER_UNTIL_TRIGGER
  REJECT
  ESCALATE
```

`APPROVED`, `DEFERRED`와 같은 결론을 Case status로 사용하지 않는다. `status=DECIDED`와 `decision_type`을 함께 기록한다.

## 6. 불확실성 하 의사결정

Evidence completeness와 Decision readiness는 별도 축이다. 데이터가 부족해도 선택이 가역적이고 피해가 제한되며 deadline이 임박했다면 조건부 진행이 합리적일 수 있다.

반대로 일부 데이터가 있어도 선택이 비가역적이고 실패를 silicon 이후에야 발견한다면 추가 근거 확보나 연기가 더 안전할 수 있다.

조언은 다음 순서로 판단한다.

1. 결정 deadline과 지연 영향을 확인한다
2. 알려진 사실, 추론, 가정과 unknown을 분리한다
3. 선택의 reversibility와 switching cost를 확인한다
4. downside, blast radius와 발견 시점을 확인한다
5. guardrail, safety margin, fallback으로 피해를 제한할 수 있는지 확인한다
6. 불확실성을 가장 많이 줄이는 최소 실험을 찾는다
7. 중단, rollback, 전환과 재검토 trigger를 정의한다
8. residual risk와 이를 수용하는 주체를 기록한다

모든 authoritative claim은 atomic claim contract를 사용한다.

```yaml
claim_id: CLM-001
statement: DDR bandwidth가 guardrail을 초과할 수 있다
epistemic_status: inference
source_refs: [MEAS-BW-001]
inference_basis: [RULE-BW-MARGIN-001]
confidence_level: medium
```

`fact`는 source가 없으면 거부한다. `inference`는 source와 inference basis가 모두 있어야 한다. LLM이 생성한 confidence 숫자를 engineering truth로 사용하지 않는다.

## 7. Role Agent의 역할과 유지 조건

### 7.1 Deterministic core가 먼저 하는 일

Agent 실행 전에 Backend가 `ObservableCasePacket`을 생성한다.

- 지정 step의 development state 재구성
- impact, dependency, deadline traversal
- evidence eligibility와 provenance 검사
- assumption과 uncertainty 분류
- reversibility, detectability, recoverability projection
- deterministic role routing 후보
- hidden-field denylist 검사와 packet hash 생성

Agent는 repository, raw fixture 또는 hidden port에 접근하지 않는다. 검증된 packet만 입력으로 받는다.

### 7.2 Agent가 추가로 하는 일

- Architecture, HW, SW, Verification, Program/Risk 관점에서 상충하는 trade-off 설명
- 명시 규칙이 놓치기 쉬운 assumption과 failure scenario 제안
- 실행 가능한 guardrail, 최소 실험과 rollback trigger 후보 작성
- 관점별 dissent와 책임 범위 보존

Decision Chair는 Lab mode의 test driver다. 회사 승인자를 대체하지 않는다.

### 7.3 Ablation과 단순화 기준

다음 구성을 같은 frozen case에 실행한다.

1. `B0`: deterministic core only
2. `B1`: deterministic core + single Architecture/System Agent
3. `B2`: deterministic core + routed independent Role Agents
4. `B3`: B2 + Challenger + simulated Chair

복잡한 topology를 유지하려면 인접 구성을 분리해서 판단한다.

- B1은 B0보다 유효한 concern, safeguard 또는 deterministic 개선을 1개 case 이상에서 추가한다
- B2는 B1보다 validation/sealed 4개 중 3개 이상에서 유효한 추가 가치를 만든다
- B3는 B2보다 validation/sealed 4개 중 3개 이상에서 Challenger/Chair 고유 가치를 만든다
- accepted unsupported authoritative claim은 0건이다
- decision policy violation은 0건이다
- case당 비용과 latency가 정해진 상한 안에 있다

각 후보는 모든 fresh case Process gate를 통과하고 baseline보다 deterministic 품질을
후퇴시키지 않아야 한다. 결과는 `keep_b3`, `release_b2`, `release_b1`, `release_b0` 중
하나로 기록한다. Replay 결과는 선택 로직의 회귀만 검증하며 실제 Agent 가치 근거로
사용하지 않는다.

## 8. Fixture와 평가 전략

### 8.1 첫 local release corpus

|Partition|Case|용도|
|---|---|---|
|Development|`CASE-VR-001`~`003`|구현과 prompt/policy 조정|
|Validation|`CASE-VR-004`~`005`|baseline 기록 후 회귀 판단|
|Sealed unseen|`CASE-HO-001`~`003`|candidate freeze 후 robustness 확인|

총 8개를 첫 release 범위로 고정한다. 12~20개 확대와 다른 scenario 추가는 I7 이후 별도 결정이다.

한 사람이 fixture 작성과 prompt 조정을 모두 수행하는 로컬 환경에서는 sealed unseen set도 독립적인 과학적 holdout이 아니다. 따라서 로컬 결과를 일반화 증거로 표현하지 않으며, 사내 pilot에서는 별도 domain reviewer가 만든 평가 set을 사용한다.

### 8.2 Corpus freeze 시점

- I1에서 `CASE-VR-001`과 schema를 완성한다
- I3 종료 전에 나머지 7개 observable, hidden, expected, rule과 manifest를 작성한다
- 첫 live-provider prompt 조정 전에 validation과 sealed unseen hash를 freeze한다
- 현재 candidate의 tuning은 development partition만 사용한다
- validation failure를 다음 candidate 수정에 사용하면 해당 case는 known regression으로만 해석한다
- sealed unseen 결과를 열어 원인을 분석하면 해당 release를 폐기한다

### 8.3 평가 분리

ReplayProvider는 contract, persistence, orchestration, UI 회귀만 증명한다. Grounding, role differentiation, decision stability와 ablation은 live output을 별도로 평가해야 한다.

Process evaluation과 Outcome evaluation도 분리한다.

- Process: 당시 observable 정보로 합리적인 결정을 구성했는가
- Outcome: simulated result가 좋았고 guardrail과 recovery가 작동했는가

상세 합격선은 `docs/readiness/04_EVALUATION_PROTOCOL.md`를 따른다.

## 9. 로컬 구현과 Gate

로컬 구현은 I0~I7만 사용한다. 상세 산출물과 명령은 `docs/readiness/01_MASTER_EXECUTION_PLAN.md`가 결정한다.

|단계|제품 관점의 완료 결과|판정|
|---|---|---|
|I0|Repository, quality command, PostgreSQL scaffold가 API key 없이 동작|GO/ITERATE|
|I1|CASE-VR-001의 development state와 contract를 deterministic하게 검증|GO/ITERATE/SIMPLIFY|
|I2|PostgreSQL 재시작 후 state와 event가 보존되고 in-memory와 일치|GO/ITERATE|
|I3|Agent 없이 Situation과 다음 행동을 한국어 UI에서 이해하고 evaluation corpus를 freeze|GO/ITERATE/SIMPLIFY|
|I4|검증된 ObservableCasePacket으로 single-role 실행과 복구가 동작|GO/ITERATE/STOP LIVE|
|I5|Multi-role와 Chair가 dissent를 보존하고 B0~B3 평가 interface가 Replay로 동작|GO/ITERATE|
|I6|Decision → Outcome → Process/Outcome evaluation 폐루프가 8개 corpus에서 동작|GO/ITERATE|
|I7|사용성, live ablation·안정성, 비용, 보안과 복구 gate를 통과하고 Agent topology를 유지·축소·제거|GO C0/KEEP LOCAL/STOP|

Gate 실패 시 다음 기능을 추가하지 않는다. 원인을 수정하거나 모델·Agent·UI 범위를 줄인 뒤 같은 gate를 다시 실행한다.

현재 로컬 구현은 실행 가능한 다음 행동, 실제 개발 진행 Digital Twin, 12-case
`eval-2026-07-14.2`, 인접 topology stop-rule과 selected-topology stability를 구현했다.
Step 4 live ablation은 B2를 선택했고 Step 5의 B2 validation x5와 sealed-unseen x3가
모두 통과해 durable dossier workflow의 기본값을 B2로 활성화했다. Post-I7 UX-A는
Development Twin의 selected-step, causal chain, commitment window, expected/observed/hidden
경계와 phase content fixture를 계약으로 고정했다. UX-B는 Backend가 우선순위·기한·막힌
개발·why-now·다음 행동을 계산하는 전용 목록 projection과 한국어 반응형 Decision Inbox를
연결했다. UX-C는 `decision-workspace.v2`를 실제 selected-step projection과 React 상세
화면에 연결해 Decision Brief, causal chain, commitment window, expected/observed 경계를
사용자 흐름으로 구현했다. UX-D는 최신 case-scoped Dossier를 Backend projection에 합성하고
선택지 비교, 의견 일치·핵심 이견·확인 필요, fact/inference/assumption/unknown과 접힌 Role
원문을 desktop/mobile 사용자 흐름으로 구현했다. UX-E는 durable decision, outcome과
evaluation을 현재 Workspace에 합성하고 Action Plan, Safeguard, Rollback, observed transition,
예상 대비 실제와 과정/결과 평가를 하나의 실행 흐름으로 연결했다. UX-F는 390/768/desktop,
200% 등가 reflow, keyboard/screen-reader semantics, partial/stale/conflict와 frozen 13-question
task를 통과했다. 이는 local agent-substitute Gate이며 human usability 또는 business value
검증을 의미하지 않는다. UX-G는 raw network 오류를 안전한 한국어 복구 문장으로 바꾸고,
과거 Step과 모바일 선택지 문맥을 URL에 보존하며, canonical action을 유지한 상태에서 설명용
용어와 hover/active/disabled 상태를 정리했다.

Project 전체 상황과 Risk provenance가 DecisionCase보다 먼저 필요하다는 검토 결과에 따라
ADR-0010이 post-I7 실행 순서를 보강한다. 기존 UX-H 도구와 hash-pinned baseline은 보존하지만,
실제 human session은 Project Operations 정보 구조를 반영한 OPS-F protocol v2 동결까지 보류했다.
현재 v2가 준비됐으므로 새 독립 관측은 이 protocol로만 수집한다.

Post-I7 후속은 다음 순서로만 진행한다.

|단계|목표|상태·Gate|
|---|---|---|
|UX-G|복구 가능한 오류, URL 문맥 보존, 한국어 우선 표현과 기본 interaction|완료|
|UX-H|공정한 fixture baseline, human task protocol과 측정 event 계약|Decision 중심 v1 도구 보존; 실제 관측 0건, OPS-F v2가 Project 중심 후속 연구를 소유|
|OPS-A|Project/Issue/Risk/Gate 경계, provenance, Agent 책임과 전환 ADR|완료; ADR-0010 Accepted|
|OPS-B|lifecycle과 risk provenance가 구별되는 Project fixture|완료; 3 Project, 17 typed event, hash manifest와 future-leakage test|
|OPS-C|Project domain, projection, API와 historical boundary|완료; PostgreSQL aggregate, reason/source policy, 5개 read API와 `at_step` parity|
|OPS-D|Project Portfolio와 Situation UX|완료; Backend 정렬 Portfolio, Situation provenance와 historical URL, 390px/desktop local task proxy PASS|
|OPS-E|Risk Detail과 기존 Decision Workspace 연결|완료; source→inference→impact→Decision/Action과 Decision 왕복 local proxy PASS|
|OPS-F|Project 중심 UX-H protocol v2, 제품 release 고정과 독립 human observation|release/rubric/E2E 도구 완료; human observation은 baseline 0/5·product 0/5에서 보류|
|UX-I|Portfolio·Situation·Workspace 정보 구조 축소·개선|완료; title-first projection, source ref 해석, 도메인 중심 copy, 390px/desktop·Axe·keyboard·full E2E PASS. Human Gate는 미통과|
|UX-J|사용자 판단과 simulated Chair를 분리해 accept/modify/reject와 anchoring 측정|완료; Demo/Evaluation mode 분리, 불변 initial/reveal/final record, builder engineering-proxy 경계와 PostgreSQL 재시작 보존|
|UX-K|전체 사용자 여정, 복구·접근성·역사 경계를 재검증하고 Local UX Release 1 동결|완료; `LOCAL-UX-RELEASE-1-5227D18`, fixture UX 완료만 주장|
|ENT-A|source-neutral record, stable identity/time, ACL/classification와 application port|완료; ADR-0012 Accepted, `enterprise-source-record.v1`, 실제 adapter/persistence 없음|
|ENT-B|versioned mapping registry, candidate provenance와 dirty fixture disposition|완료; ADR-0013 Accepted, 10개 normal/dirty pattern과 `ACCEPT/QUARANTINE/REJECT` 검증|
|ENT-C|idempotent sync, cursor/checkpoint, bounded retry, tombstone와 reconciliation|완료; ADR-0014 Accepted, one-shot/resume 결정성 및 stale-content 보호 검증|
|ENT-D~F|dry-run/quarantine, security emulator와 handoff kit|ENT-D가 다음; 실제 company data/vendor API/auth 없음|

UX-H는 observable fixture hash와 source selector로 고정한 Jira/Confluence형 baseline pack,
canonical 8개와 Development Twin 5개 task, `usability-session.v1` event/result 계약과
검증·요약 CLI까지 구현했다. 실제 사람의 답변·시간은 만들지 않았으며 dry-run summary는
`not_ready`와 `no_business_claim`을 반환한다. condition별 proxy/domain reviewer 5개 이상을
확보하기 전에는 원칙적으로 UX-I를 시작하지 않는다. 2026-07-23 owner 결정으로 human observation을
0/5 상태에서 보류하고 UX-I를 engineering-proxy로 진행한다. 이 예외는 human Gate나 business claim을
열지 않는다. 새 Project 중심 human 관측을 재개하면 OPS-F v2 또는 변경 제품용 새 frozen release를
사용하며, 사내 source·권한·승인은 C0에서 별도로 연다.

UX-I는 owner가 승인한 engineering-proxy 범위에서 raw 기준점/source ID와 구현 중심 copy라는
사전 지정 문제만 개선했고 `UX-I-PRODUCT-87D49D7` release로 동결했다. UX-J는 advice 공개 전 builder의
초기 판단과 공개 후 `accept/modify/reject`를 별도 불변 record로 보존한다. 현재 record는
`engineering_proxy_only`이며 사람 평가로 집계하지 않는다. 구현은 `UX-J-PRODUCT-218C095`로
동결했다. UX-K는 이 전체 흐름을 responsive, accessibility, partial/stale/conflict,
current/historical E2E와 함께 `LOCAL-UX-RELEASE-1-5227D18`로 재동결했다. 이는 local fixture
engineering Gate이며 사람 사용성이나 비즈니스 가치를 입증하지 않는다. 다음 고정 단계는 ENT-A이고,
ADR-0012는 `enterprise-source-record.v1`과 source-neutral port를 승인했고 ENT-A를 완료했다.
ADR-0013은 versioned mapping candidate와 synthetic dirty corpus를 승인해 ENT-B를 완료했다.
ADR-0014는 cursor/page token, content-hash idempotency, bounded retry, tombstone/restricted 우선
reconciliation을 persistence-independent checkpoint로 승인해 ENT-C를 완료했다. 다음 단계 ENT-D
전에는 canonical import, durable quarantine/resolution이나 dry-run write path를 구현하지 않는다.

```text
B2 validation 10/10 + sealed-unseen 6/6 PASS
  → persisted runtime topology B2 활성화
  → legacy dossier는 migration에서 B3로 보존
```

## 10. 기술 원칙

- Domain은 FastAPI, SQLAlchemy, provider SDK와 UI label을 import하지 않는다
- PostgreSQL durable state를 Agent worker보다 먼저 구현한다
- Frontend는 decision readiness, risk, agreement와 allowed action을 계산하지 않는다
- Agent output은 schema와 deterministic policy를 통과하기 전 candidate다
- hidden repository는 Outcome/Evaluation과 authoring CLI만 접근한다
- API는 `/api/v1/decision-cases`와 `/api/v1/runs`를 사용한다
- root `pyproject.toml` 하나가 `backend/src` package를 관리한다
- OpenAPI에서 Frontend TypeScript client를 생성한다
- Graph/vector DB와 agent framework는 측정 근거가 생기기 전 도입하지 않는다
- 기존 `E:\56_Codex_SoC_Operational_Ontology` 코드는 새 test와 ADR 없이 port하지 않는다

## 11. 사외 준비와 사내 전환

사내 전환은 로컬 UX 구현의 연장이 아니라 별도 승인 범위다. 다만 사내에서 connector를 처음부터
개발하지 않도록 UX-K 뒤 실제 data 없이 가능한 `ENT-A~F`를 사외에서 먼저 완료한다.

### ENT-A~F. 사외 Enterprise Preparation

ENT-A는 source-neutral envelope와 application port, ENT-B는 versioned mapping registry와
source-span candidate, ENT-C는 deterministic checkpoint/reconciliation까지 완료했다. 현재 다음
단계는 ENT-D no-write dry-run, quality report와 quarantine contract다.

- source-neutral record, stable external identity와 enterprise time 계약
- vendor SDK와 분리된 read-only source port
- synthetic dirty export fixture와 mapping registry
- cursor, content hash, idempotency, retry, tombstone와 reconciliation
- no-write dry-run, canonical diff, quality report와 quarantine
- opaque ACL/classification policy emulator와 restricted-source leakage test
- Jira/Confluence mapping template, 환경 worksheet와 사내 cutover runbook

사외 단계에는 실제 Jira/Confluence API 호출, credential, 회사 field ID, 실제 user/group ACL과
write-back을 넣지 않는다. 상세 순서와 Gate는
`internal_docs/26.07.23 UX 마무리 및 사내 데이터 전환 실행 계획.md`가 소유한다.

### C0. 환경과 데이터 경계 확인

- Jira/Confluence 제품과 version, 인증 방식 확인
- 배포 network, secret, model provider와 audit 정책 승인
- source ACL, 삭제, retention과 export 규칙 확정
- pilot owner, human decision authority와 대상 workflow 지정
- ENT dry-run에 승인된 sanitized export를 넣어 schema와 mapping 적합성 먼저 확인
- allowlist 한 Project/Space에서만 read-only connector smoke와 sync/reconciliation 검증

### C1. Read-only pilot

- 한 과제, 한 Video Recording review workflow
- allowlist project/space와 5~10명 이내 사용자
- recommendation만 제공하고 실제 결정은 사람이 기록
- 최소 10개 historical case와 10개 prospective case를 방향성 표본으로 사용
- historical case는 난이도·severity가 비슷한 matched pair로 비교
- prospective case는 업무상 가능하면 사용자 또는 review 순서를 교차하는 crossover로 비교
- case 제외 조건과 난이도·severity 층화를 시스템 결과를 보기 전에 고정
- 평균만 보고하지 않고 median, 사분위 범위와 case별 분포를 함께 기록
- 표본이 작으면 business proof가 아니라 directional signal로 보고

초기 value metric은 다음처럼 정의한다.

|Metric|시작|종료|집계|
|---|---|---|---|
|Situation-to-Decision Time|review 시작|human decision 기록|case별 elapsed time의 median과 분포|
|Evidence Pack Preparation Time|evidence 수집 시작|review-ready 선언|case별 active effort와 elapsed time 분리|
|Critical Impact Recall|review 결과 확정|expert reference set 확정|식별한 critical item / reference critical item|
|Safeguard Completeness|recommendation 생성|human review 완료|required guardrail/trigger/owner/verification 충족률|
|Advice Adoption|advice 확인|human decision 기록|accept/modify/reject와 사유, 품질의 보조 지표|

Critical impact reference set은 시스템 결과를 보지 않은 domain reviewer가 먼저 freeze한다. 초기 개선 목표값은 baseline 5개 이상을 측정한 뒤, 시스템 사용 결과를 보기 전에 pilot protocol에 고정한다. Adoption과 만족도만으로 business value를 판정하지 않는다.

### C2. Controlled write-back

C1에서 가치와 보안 gate를 통과한 뒤에만 연다.

- Jira/Confluence draft preview
- named human approval
- idempotency key와 audit
- rollback 또는 compensation
- 허용 field와 action allowlist

## 12. 주요 위험과 중단 기준

|위험|조기 신호|대응 또는 중단 기준|
|---|---|---|
|Ontology 확대|새 객체는 늘지만 CASE-VR-001이 끝나지 않음|첫 질문에 필요 없는 객체 승격 금지|
|Fixture theater|expected answer에만 맞고 live output이 불안정|일반화 주장 금지, 사내 독립 평가 전 확장 중단|
|Role collapse|여러 Agent가 같은 의견을 반복|Ablation 실패 시 single-agent로 축소|
|Agent 과신|source 없는 authoritative claim 발생|accepted 1건이라도 있으면 release 실패|
|Data 부족 시 과도한 block|가역 case도 모두 defer|decision posture rule과 case 분포 재설계|
|과도한 proceed|비가역·high downside에서도 조건 없이 진행|policy violation 1건이라도 있으면 release 실패|
|UI 복잡도 재발|raw graph/ID 없이 질문에 답하지 못함|projection과 화면을 줄이고 I3/I7 재검증|
|Hidden leakage|prompt, API, log에 hidden 값 노출|즉시 release 중단과 fixture key rotation|
|비용·지연 과다|multi-role lift보다 비용 증가가 큼|Role 수와 revision 제거|
|사내 가치 미확인|사용 후기만 있고 workflow telemetry가 없음|write-back과 domain 확장 금지|

## 13. 확정 결정과 미확정 항목

### 13.1 로컬 구현에서 확정

- Primary persona: Multimedia System/Architecture Reviewer
- 첫 workflow: Video Recording Scenario Change Review
- 첫 case: CASE-VR-001 UHD60 EIS power-gap
- 데이터: synthetic fixture only
- 로컬 승인: simulated Chair, 실제 권한 없음
- 구현 단계: I0~I7
- 현재 단계: ENT-C idempotent sync와 reconciliation 완료; OPS-F human observation은 baseline 0/5·product 0/5에서 보류
- 후속 순서: ENT-D~F 사외 준비, 그 뒤 사내 C0/C1
- release topology: B2 independent routed Role Agents, deterministic core decision
- CI provider: ReplayProvider
- live provider: 구성 가능한 OpenAI Responses API adapter
- corpus v2: development regression 8, validation 2, sealed unseen 2

### 13.2 사내 전환 전에 확인

- 실제 workflow와 Primary persona 가설이 맞는가
- 현재 evidence 준비, 상황 재구성, 결정에 걸리는 baseline은 얼마인가
- Jira/Confluence 배포 형태, version, 인증과 API 정책은 무엇인가
- 허용되는 model provider와 data classification은 무엇인가
- source ACL을 어떤 방식으로 계승하는가
- pilot owner, data owner와 human decision authority는 누구인가

이 질문은 완료된 로컬 Replay gate를 소급해 막지 않는다. C0 시작 전에는 모두 답해야 한다.

## 14. 참고 자료

Active planning documents:

- `docs/PLAN_INDEX.md`
- `docs/readiness/00_IMPLEMENTATION_READINESS_RESULT.md`
- `docs/readiness/01_MASTER_EXECUTION_PLAN.md`
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
- `internal_docs/26.07.23 OPS-F Human Observation 보류 결정.md`
- `internal_docs/26.07.24 UX-I Engineering Proxy 변경 Backlog.md`
- `internal_docs/26.07.24 UX-I Engineering Proxy 구현 및 검증 보고서.md`
- `internal_docs/26.07.24 UX-J 조언 영향 평가 구현 및 검증 보고서.md`
- `internal_docs/26.07.24 UX-K Local UX Release 1 구현 및 검증 보고서.md`
- `docs/decisions/ADR-0010-project-operations-and-risk-provenance.md`
- `docs/decisions/ADR-0011-evaluation-response-and-advice-disclosure.md`
- `docs/decisions/ADR-0012-source-neutral-enterprise-ingestion-boundary.md`
- `internal_docs/26.07.24 ENT-A Source-neutral Ingestion 계약 구현 및 검증 보고서.md`
- `docs/decisions/ADR-0013-versioned-enterprise-mapping-candidates.md`
- `internal_docs/26.07.25 ENT-B Mapping Registry 및 Dirty Fixture 구현 보고서.md`

Review and historical context:

- `docs/PLAN_REVIEW_2026-07-11.md`
- `docs/ADDITIONAL_REQUIREMENTS_REVIEW.md`
- `docs/OLD_PROJECT_ASSET_REVIEW.md`
- `internal_docs/26.06.18 SoC ontology (ChatGPT).md`
- `internal_docs/26.07.05 비지니스 가치 논의.md`
- `D:/YHJOO/100_SoC_Operational_Ontology/07_Claude_Tycoon/01_Ideation/Ref00_project_brief.md`
- `D:/YHJOO/100_SoC_Operational_Ontology/07_Claude_Tycoon/01_Ideation/Ref01_problem_statement.md`
- `D:/YHJOO/100_SoC_Operational_Ontology/07_Claude_Tycoon/01_Ideation/Ref02_poc_scope.md`
- `D:/YHJOO/100_SoC_Operational_Ontology/07_Claude_Tycoon/01_Ideation/Ref03_SoC digital twin review.md`
