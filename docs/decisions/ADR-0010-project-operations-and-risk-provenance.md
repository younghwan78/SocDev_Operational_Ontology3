# ADR-0010: Project Operations와 Risk Provenance를 Decision Workspace의 상위 문맥으로 둔다

> 상태: Accepted
> 날짜: 2026-07-21
> 범위: local fixture-only PoC, post-I7 OPS-A~OPS-F

## 맥락

현재 제품은 한 `ObservableCase` 안에서 개발 Track, WorkItem, Milestone, Evidence,
Alternative와 Decision lifecycle을 재구성한다. 이 구조는 하나의 결정을 깊게 검토하고,
Role별 이견, simulated Chair, Action, Outcome과 Evaluation을 연결하는 데는 충분하다.

그러나 사용자가 과제별로 다음 질문을 먼저 답하려면 DecisionCase보다 상위 문맥이 필요하다.

- 과제 전체는 지금 어떤 상태인가?
- 어떤 Track과 Issue가 다음 Gate를 위협하는가?
- Risk는 어떤 Event, Evidence gap과 dependency에서 나왔는가?
- 여러 DecisionCase와 Action이 같은 Risk를 어떻게 다루는가?
- 지난 review 이후 무엇이 개선되거나 악화됐는가?

현재 `ObservableCase`에는 `project_id`가 없고 `blocker`는 WorkItem 문자열이다. Agent의
`RiskAssessment`도 Role review의 candidate이지 Project Risk lifecycle을 가진 canonical
객체가 아니다. 이 상태에서 Project Situation UI를 먼저 만들면 Frontend가 서로 다른
DecisionCase를 임의로 묶거나 risk score를 계산하게 된다.

## 결정

### 1. 제품 흐름

기존 Decision Workspace를 교체하지 않고 다음 상위 흐름을 추가한다.

```text
Project Portfolio
  → Project Situation
  → Issue/Risk Detail
  → existing Decision Workspace
  → Action / Outcome / Evaluation
```

`A0~A4`는 내부 정보 설계 원칙으로만 사용한다. 사용자가 `A1`, `A2` 같은 고도를 직접
선택하게 하지 않고 `과제 상황`, `주요 위험`, `선택지 검토`, `근거 보기`로 표현한다.

GO/NO-GO는 명시적 Gate policy와 승인 문맥 안에서만 사용한다. 일반 Project 화면은
Backend가 근거와 함께 계산한 `ProjectAttention`을 사용한다.

### 2. 최소 운영 객체

OPS 범위의 최소 객체와 책임은 다음과 같다.

|객체|책임|
|---|---|
|`DevelopmentProject`|과제 identity, lifecycle stage, 현재 Step과 Project-level reference|
|`DevelopmentTrack`|Architecture/HW/SW/Verification 등 병렬 개발 흐름|
|`WorkItem`|owner, dependency, 계획 Step과 현재 진행 상태|
|`Milestone`|과제 기준점; `kind=GATE`일 때 명시적 exit policy를 참조|
|`DevelopmentIssue`|이미 관측된 현재 또는 과거 문제|
|`ProjectRisk`|현재 상태가 미래 손실로 이어질 가능성과 treatment 상태|
|`Evidence`/`Claim`|관측 근거와 fact/inference/assumption/unknown 경계|
|`DevelopmentEvent`|상태 변경의 effective/observed Step, 원인과 영향 객체|
|`DecisionCase`|Risk를 처리하기 위해 선택이 필요한 bounded question|
|`DevelopmentAction`|결정을 실행하는 owner/due/verification/rollback 단위|

`GateReview`를 별도 aggregate로 만들지 않는다. 첫 vertical slice에서는 `Milestone(kind=GATE)`와
그 Gate를 다루는 DecisionCase/Event 조합으로 표현한다. 별도 lifecycle이 실제로 필요하다는
fixture와 UI 요구가 생길 때만 승격한다.

### 3. 의미 경계

|용어|정의|
|---|---|
|Blocker|현재 WorkItem 진행을 실제로 막는 관측 상태|
|Issue|이미 발생하거나 관측된 문제|
|Risk|Issue, Event, dependency 또는 Evidence gap에서 파생되는 미래 손실 가능성|
|Uncertainty|아직 알 수 없거나 확인되지 않은 부분|
|DecisionCase|Risk treatment를 선택해야 하는 질문|
|Action|선택을 실제 개발 작업으로 변환한 것|
|Outcome|Action 이후 관측된 결과|

Issue와 Risk를 하나의 문자열로 합치지 않는다. Risk가 실제로 발생하면 `REALIZED`로 바꾸고
관련 Issue를 참조한다. Evidence 부족 자체는 blocker가 아니며, commitment window와 downside에
따라 guarded trial, minimum evidence collection 또는 deferral의 입력이 된다.

### 4. 예약 상태와 정렬 원칙

OPS-B/OPS-C에서 사용할 예약 enum은 다음과 같다.

```text
ProjectAttention = ON_TRACK | WATCH | AT_RISK | BLOCKED
IssueStatus       = OPEN | MITIGATING | RESOLVED
RiskStatus        = OPEN | TREATING | ACCEPTED | REALIZED | CLOSED
RiskLevel         = LOW | MEDIUM | HIGH | CRITICAL
MilestoneKind     = CHECKPOINT | GATE | RELEASE
```

`ProjectAttention`과 `RiskLevel`은 source fixture가 임의 점수로 지정하지 않는다. Backend의
versioned deterministic policy가 observable state에서 계산하고, projection은 항상
`attention_reasons`와 `source_refs`를 함께 반환한다.

Risk 목록은 `impact × likelihood` 숫자 곱으로 정렬하지 않는다. 첫 policy는 다음의 명시적
ordinal 정보와 Gate/commitment proximity를 사용한다.

- downside
- blast radius
- urgency
- reversibility
- detectability
- evidence sufficiency/freshness
- affected milestone와 dependency path

동률 순서까지 재현 가능한 deterministic ordering을 사용하되 UI에는 composite score가 아니라
상태, 이유와 영향 경로를 표시한다. 정량 likelihood를 도입하려면 calibration source와 별도 ADR이
필요하다.

### 5. Risk provenance

모든 `ProjectRisk`는 다음 경로 중 하나 이상을 가져야 한다.

```text
DevelopmentEvent / Evidence gap / DevelopmentIssue
  → inference rule 또는 Agent hypothesis
  → ProjectRisk
  → affected WorkItem/Track/Milestone
  → DecisionCase 또는 treatment Action
```

- `fact`는 eligible source가 필요하다.
- deterministic `inference`는 `source_refs`와 `inference_basis`가 필요하다.
- Role Agent 제안은 `assumption` 또는 별도 hypothesis candidate이며 canonical Risk를 직접
  생성하거나 상태를 변경하지 않는다.
- Critic과 simulated Chair는 candidate의 근거·누락·완화책을 검토하지만 Project truth를
  소유하지 않는다.
- Frontend는 risk, attention, urgency 또는 causal path를 재계산하지 않는다.

### 6. Aggregate와 전환 전략

목표 source-of-truth는 `DevelopmentProject` aggregate다. DecisionCase는 `project_id`와
`source_issue_ids`, `treated_risk_ids`, `affected_work_item_ids`를 참조한다.

현재 `observable-case.v1`은 OPS-A에서 변경하지 않는다. 전환은 다음 순서로 수행한다.

1. OPS-B에서 `development-project.v1` authoring fixture와 validator를 추가한다.
2. 기존 CASE fixture와 hash-pinned UX-H baseline은 회귀 기준으로 유지한다.
3. OPS-C에서 Project projection과 DecisionCase reference 계약을 구현한다.
4. required field를 기존 case payload에 추가해야 한다면 새 major와 migration을 사용한다.

OPS-B fixture를 읽기 위해 현재 runtime domain을 억지로 확장하지 않는다. OPS-C 전까지 새
Project fixture는 authoring/validation 입력이며 현재 제품 API의 구현 완료를 뜻하지 않는다.

### 7. UX와 예약 resource

OPS-C 이후의 예약 Frontend route와 query resource는 다음과 같다.

```text
/projects
/projects/:projectId
/projects/:projectId/risks/:riskId

GET /api/v1/projects
GET /api/v1/projects/{project_id}/situation
GET /api/v1/projects/{project_id}/risks
GET /api/v1/projects/{project_id}/risks/{risk_id}
GET /api/v1/projects/{project_id}/timeline
```

모든 historical query는 기존 규칙대로 `at_step`을 사용하며 미래 Event, Evidence, Risk state,
Decision/Outcome을 노출하지 않는다. 이 resource는 OPS-A 시점에는 예약 계약이며 executable
API가 아니다.

### 8. `world.yaml` 참조 정책

사용자가 제공한 다음 파일은 OPS-B에서 필요할 때 참고할 수 있는 **event idea catalog**로
승인한다. 이 파일의 Project 구조, 역할 구성, risk score, activity log 또는 event 개수는
OPS-B 요구사항이 아니다.

```text
E:\57_Claude_SoC_DigitalTwin\OperationalOntology\data\world.yaml
SHA-256: 108E5BFC2311B90E0264ED470D081920F4F414CBE3072F663DEC47ABEBA72759
```

OPS-B가 참고할 수 있는 범위는 top-level `events` 항목의 situation, span, propagation,
evidence, missing evidence와 option trade-off뿐이다. Event는 다음 UX 질문을 더 잘 검증하는
경우에만 선택한다.

- lifecycle이 다른 Project의 위험을 한눈에 구별할 수 있는가?
- 관측 Issue와 미래 Risk, Evidence gap을 구별할 수 있는가?
- Risk가 WorkItem/Track/Milestone/Decision에 미치는 경로를 추적할 수 있는가?
- field evidence, pre-silicon inference와 model/lesson assumption의 차이를 이해할 수 있는가?
- 해결, 악화, 지연 도착 Evidence와 cross-project lesson 중 필요한 변화를 볼 수 있는가?

고정된 event 수를 목표로 하지 않는다. OPS-B는 위 UX coverage를 만족하는 가장 작은
fixture set을 만들고, 의미가 중복되는 event는 제외한다. 파일을 runtime dependency로 만들거나
verbatim 복사하지 않는다.

- 선택한 event idea는 local synthetic Project 문맥에 맞게 다시 작성한다.
- 긴 Role LLM prose, `reasoning_src`, dice와 사전 계산된 risk score는 가져오지 않는다.
- 실제 회사명, 사람, issue key 또는 비밀정보를 추가하지 않는다.
- week는 canonical logical Step으로 변환하고 effective/observed/available 시점을 분리한다.
- activity text가 아니라 실제 WorkItem/Milestone/Evidence before/after change를 생성한다.
- cross-project propagation은 source Event와 target Risk/WorkItem link로 명시한다.
- 새 fixture마다 positive/negative/historical-boundary test와 immutable hash를 추가한다.

외부 reference가 바뀌어도 이미 committed된 fixture는 자동 변경되지 않는다. 다른 revision을
반영하려면 hash와 adaptation note를 갱신한다.

### 9. 실행 순서

```text
OPS-A Scope/ADR
  → OPS-B Project-centered fixture
  → OPS-C Domain/Projection/API
  → OPS-D Portfolio/Situation UX
  → OPS-E Risk Detail/Decision linkage
  → OPS-F UX-H protocol v2 + independent human observation
  → UX-I / UX-J
```

기존 UX-H tooling과 관측 0건은 보존하되 human session 실행을 OPS-F까지 보류한다. 새 상위
정보 구조를 반영하지 않은 baseline으로 사람 데이터를 수집해 UX-I를 시작하지 않는다.

## OPS-B Gate

OPS-B는 다음 조건을 모두 만족해야 종료한다.

- Project fixture가 lifecycle, evidence strength, commitment window와 risk pattern에서
  충분히 구별된다.
- 선택한 event thread가 Project Situation, Risk provenance와 historical comparison의 UX
  질문을 각각 검증하며 의미가 중복되지 않는다.
- field evidence가 강한 양산, pre-silicon 불확실성이 큰 HW closure, model/lesson 중심의 Spec
  단계가 포함된다.
- open/late/received evidence, resolved/realized risk, rework, resource conflict와 cross-project
  propagation 중 목표 UX에 필요한 대표 패턴이 포함된다.
- Issue → Risk → Milestone/Decision path를 fixture만으로 검증할 수 있다.
- 모든 historical reconstruction이 future information leakage test를 통과한다.
- 기존 12-case regression과 UX-H baseline hash는 의도 없이 변경되지 않는다.

## 제외한 대안

### 기존 DecisionCase를 Project처럼 그룹화

같은 blocker 문자열과 title만으로 case를 묶으면 source identity와 lifecycle을 복구할 수 없고,
Frontend 추론을 만들기 때문에 제외한다.

### full ontology와 process mining을 먼저 구현

첫 Project Situation 질문에 필요하지 않은 객체와 인프라가 늘어나므로 제외한다. Project Event
model이 fixture와 UX에서 입증된 뒤 별도 Gate로 검토한다.

### Role Agent가 Project Risk를 직접 결정

설명 가능한 observable truth와 hypothesis 경계가 무너지므로 제외한다. Agent는 누락 영향,
완화책과 반론을 제안하는 역할로 제한한다.

## 결과

장점은 현재 Decision Workspace를 보존하면서 사용자가 전체 과제에서 위험의 위치와 근거를
먼저 이해할 수 있다는 점이다. 반면 새 aggregate, fixture version, projection과 migration이
필요하므로 OPS-B와 OPS-C를 분리하고 각 단계 Gate 전에는 UI를 구현하지 않는다.
