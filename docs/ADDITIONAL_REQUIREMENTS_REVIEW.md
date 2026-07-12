# 추가 고려사항 검토 및 반영 방향

> 검토일: 2026-07-10  
> 기준 계획: `PROJECT_PLAN.md`  
> 참고 문서: `Ref00_project_brief.md`, `Ref01_problem_statement.md`, `Ref02_poc_scope.md`, `Ref03_SoC digital twin review.md`

## 1. 사용자 피드백 요약

### 1. 실제 개발 진행이 충분히 모델링되지 않음

기존 시스템은 Project, Scenario, Event, Evidence를 연결했지만 실제 개발이 어떻게 진행되고 지연·변경·재작업되는지를 충분히 표현하지 못했다. Role Agent는 주어진 snapshot을 보고 필요한 근거를 요구했지만 다음 질문에 답하기 어려웠다.

- Architecture, HW, SW, Verification이 각각 어느 단계인가?
- 서로 다른 track의 준비 상태가 어떻게 다른가?
- 어떤 작업이 다른 작업을 기다리고 있는가?
- 지금 바꿀 수 있는 것은 무엇이고 변경 가능 시점이 지난 것은 무엇인가?
- 결정을 늦추면 어떤 milestone 또는 후속 작업이 지연되는가?
- 임시 workaround가 언제 technical debt나 재작업으로 돌아오는가?
- 결정과 action이 실제 개발 상태를 어떻게 바꾸었는가?

### 2. 데이터가 부족해도 결정해야 하는 현실이 반영되지 않음

기존 구조는 evidence가 부족하면 confidence를 낮추고 decision을 block하는 데 강했다. 하지만 실제 개발에서는 측정·예측 data가 준비되기 전에 결정을 내려야 하는 경우가 많다.

필요한 것은 “데이터가 없으므로 판단 불가”만이 아니라 다음 유형의 조언이다.

- 변경을 되돌릴 수 있으므로 제한된 범위에서 먼저 진행
- 손실이 크고 되돌리기 어려우므로 결정 연기
- schedule상 기다릴 수 없으므로 safety margin과 rollback 조건을 붙여 진행
- 모든 시나리오에서 상대적으로 안전한 robust option 선택
- 향후 정보가 들어왔을 때 갈아탈 수 있도록 option을 보존
- 가장 불확실성을 많이 줄이는 최소 측정 또는 실험만 먼저 수행
- 위험을 없앨 수 없으면 영향을 제한하고 탐지·복구 가능성을 높임

### 3. UI가 복잡하고 영어 중심

기존 UI는 많은 기능과 object를 직접 노출하면서 portfolio, weekly, timeline, evidence, risk 등 여러 화면으로 확장됐다. 이는 시스템이 가진 정보를 보여주지만 사용자가 지금 내려야 하는 결정을 빠르게 이해하기는 어렵다.

새 UI는 한국어를 기본으로 하고 한 화면에서 다음 네 질문에 먼저 답해야 한다.

1. 지금 무엇을 결정해야 하는가?
2. 왜 지금 결정해야 하는가?
3. 어떤 선택지가 있고 위험은 무엇인가?
4. 선택 후 무엇을 확인하고, 언제 철회해야 하는가?

## 2. 참고 문서에서 유지할 것

- 맥락 파편화가 핵심 문제라는 정의
- synthetic development world로 먼저 검증한다는 접근
- 상용, 실행/EVT, architecture exploration의 의사결정 차이
- 세대 간 issue/request/lesson 흐름
- Scenario와 IP/system block의 연결
- power, performance, area, schedule, resource, business trade-off
- structured output, validator, human final authority
- 설명 문서, contract, fixture, task를 분리하는 문서화 원칙

## 3. 참고 문서에서 수정할 것

### 3.1 Project phase를 Development Progress model로 확장

Project에 `phase: evt_development` 같은 단일 값을 주는 것으로 끝내지 않는다. 한 Project 안에 여러 Development Track을 둔다.

```text
Architecture Track
HW/RTL Track
SW/FW/HAL Track
Verification Track
Measurement/Characterization Track
Customer/Product Track
```

각 track은 독립적으로 진행되며 서로 다른 상태와 dependency를 가진다.

### 3.2 Role Agent 중심에서 Work/Decision 중심으로 변경

Role은 owner와 관점으로 남기되 시스템의 주축은 아니다.

```text
기존 중심:
Event → Role Agent별 의견 → Management Agent 판단

신규 중심:
Development State + Decision Window + Uncertainty
  → Alternative/Trade-off
  → Human Decision
  → Work/Action State Change
  → Outcome
```

### 3.3 Evidence confidence와 Decision readiness 분리

Evidence가 약하다는 사실만으로 decision을 자동 block하지 않는다.

```text
Evidence Completeness
  무엇을 얼마나 알고 있는가?

Decision Urgency
  언제까지 결정해야 하는가?

Reversibility
  잘못되었을 때 되돌릴 수 있는가?

Downside / Blast Radius
  실패했을 때 피해가 얼마나 크고 퍼지는가?

Detectability / Recoverability
  문제를 얼마나 빨리 발견하고 복구할 수 있는가?

Mitigation Strength
  guardrail, fallback, safety margin이 있는가?
```

이 요소를 함께 보고 decision posture를 정한다.

## 4. 추가해야 할 핵심 모델

### 4.1 Development Progress

|객체|설명|
|---|---|
|DevelopmentTrack|Architecture, HW, SW, Verification 등 독립 진행 축|
|WorkItem|실제 수행해야 하는 분석, 구현, 검증, 측정 작업|
|Deliverable|spec, RTL drop, SW build, report, test result 등|
|Dependency|선행/후행, interface, resource, evidence 의존성|
|Milestone|검토 또는 완료 기준점|
|DevelopmentEvent|시작, 완료, 실패, 변경, block, reopen 등의 사건|
|DecisionWindow|결정 가능 시점, deadline, 지연 비용|
|ResourceConstraint|인력, 장비, simulation, silicon, 일정 제약|
|TechnicalDebt|임시 workaround나 미해결 가정의 미래 비용|

### 4.2 Uncertainty와 Risk

|객체/개념|설명|
|---|---|
|Uncertainty|무엇을 모르고 왜 모르는지|
|Assumption|결정을 위해 잠정적으로 참으로 두는 조건|
|RiskScenario|가정이 틀릴 때 발생 가능한 결과|
|Mitigation|발생 가능성 또는 영향을 줄이는 조치|
|Guardrail|진행을 허용하는 제한 조건|
|Trigger|재검토, 중단, rollback을 시작하는 관측 조건|
|Contingency|문제 발생 시 실행할 대응|
|ResidualRisk|조치 후에도 남는 위험|
|RiskAcceptance|누가 어떤 이유로 남은 위험을 수용했는지|

### 4.3 Decision Strategy

초기 조언 유형은 다음으로 제한한다.

```text
APPROVE
APPROVE_WITH_GUARDRAILS
RUN_REVERSIBLE_TRIAL
COLLECT_MINIMUM_EVIDENCE
DEFER_UNTIL_TRIGGER
REJECT
ESCALATE
```

각 조언은 다음을 반드시 포함한다.

- 지금 결정해야 하는 이유 또는 기다려도 되는 이유
- 현재 알려진 것과 모르는 것
- 핵심 가정
- 선택지별 upside/downside
- reversibility와 전환 비용
- guardrail과 safety margin
- rollback 또는 재검토 trigger
- 필요한 최소 추가 evidence
- 선택 후 verification 계획
- residual risk와 risk owner

## 5. Synthetic Fixture 설계 변경

기존의 “정상 case, 모순 evidence, evidence 부족으로 abstain” 세 종류만으로는 부족하다.

최소 다음 case를 포함한다.

### Case A. 충분한 evidence로 결정

- KPI와 과거 issue가 일치
- option의 영향과 검증 계획이 명확
- 일반적인 approve/approve with constraint

### Case B. 데이터 부족이지만 가역적이므로 진행

- HW 변경은 없고 SW knob/feature flag로 제한 가능
- deadline이 measurement 준비보다 빠름
- limited rollout, guardrail, rollback trigger를 붙여 진행

### Case C. 데이터 부족하고 비가역적이므로 연기

- RTL/area/interface 변경으로 되돌리기 어려움
- downside가 크고 silicon 이후에야 발견 가능
- 최소 evidence 확보 또는 escalation 전까지 defer

### Case D. Evidence가 충돌해 판별 실험 수행

- 과거 project와 현재 model의 방향이 다름
- 전체 측정이 아니라 두 가설을 구분하는 최소 실험 추천

### Case E. Customer/spec 불확실성에서 option 보존

- 미래 고객 요구가 확정되지 않음
- 지금 full implementation 대신 interface/area/fallback option을 보존
- trigger가 발생하면 다음 commitment 단계로 이동

### Case F. 일정 때문에 기술 부채를 수용

- 정식 fix는 milestone을 넘김
- workaround를 선택하되 expiry, owner, verification, 차기 project 반영 조건을 기록

각 case에는 Development Track, WorkItem, Dependency, Decision Window, Resource Constraint, 실제 Outcome을 포함한다.

## 6. 한국어 중심 단순 UI

### 6.1 MVP 화면 수

MVP의 주요 화면은 최대 세 개로 제한한다.

```text
1. 결정 목록
2. 결정 검토
3. Fixture/평가 관리 — 개발자용
```

### 6.2 결정 검토 화면의 기본 순서

```text
[무엇을 결정해야 하나]
결정 질문 / 결정 기한 / 현재 개발 단계

[권고]
권고 유형 / 핵심 이유 / 남은 위험

[현재 개발 상황]
track별 진행 / blocker / 다음 milestone / 변경 가능 시점

[선택지 비교]
효과 / 위험 / 일정 / 되돌리기 / 필요한 조건

[안전하게 진행하려면]
guardrail / 최소 측정 / rollback trigger / 후속 action

[상세 보기]
근거 / 가정 / timeline / ontology link / raw ID
```

### 6.3 표현 원칙

- 사용자 문구와 navigation은 한국어가 기본이다.
- ISP, KPI, RTL처럼 조직에서 통용되는 약어만 영문을 유지한다.
- 내부 canonical field는 UI에서 한국어 label로 표시한다.
- raw ID, JSON, graph는 기본 화면에 노출하지 않는다.
- role별 card/tab을 만들지 않고 의견은 결정 쟁점별로 합친다.
- risk를 색상만으로 표현하지 않고 텍스트와 원인을 함께 표시한다.
- 첫 화면에는 핵심 5개 이내의 요약만 표시한다.
- evidence graph, source metadata, 전체 timeline은 펼쳐보기로 제공한다.
- 사용자의 다음 행동은 화면당 하나의 primary action으로 명확히 한다.

## 7. 제품 성공 기준의 변경

기존 evidence 중심 지표에 다음을 추가한다.

- 현재 개발 상태 재구성 시간
- dependency/blocker 식별 누락률
- 결정 지연 비용 또는 milestone 영향 설명 가능 여부
- 불확실성 유형과 핵심 가정 식별 정확도
- reversibility/guardrail/rollback 제안의 유용성
- 데이터가 부족한 case에서 과도한 block 또는 과도한 진행 비율
- 실제 outcome 후 조언 적합성 평가
- 한국어 UI에서 핵심 결정 질문 파악 시간
- 사용자가 graph/raw ID 없이 다음 action을 선택할 수 있는지

## 8. 최종 반영 결론

프로젝트의 중심 문장을 다음처럼 보완한다.

> **SoC 개발의 진행 상태와 불확실성을 운영 온톨로지로 재현하고, 데이터가 충분한 경우에는 근거 기반 판단을, 데이터가 부족한 경우에는 가역성·영향·일정·완화책을 고려한 저후회 결정을 조언한다.**

이 정의는 “데이터가 많아지면 판단이 완성된다”는 가정을 버린다. 데이터는 중요한 입력이지만 실제 제품 가치는 제한된 시간과 정보 안에서 다음 행동을 더 안전하게 선택하도록 돕는 데 있다.
