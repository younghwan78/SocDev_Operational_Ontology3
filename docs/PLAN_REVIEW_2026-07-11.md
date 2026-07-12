# 전체 계획 재검토 및 개선 결과

> 상태: Completed  
> 검토일: 2026-07-11  
> 대상: `PROJECT_PLAN.md`, `docs/readiness`, 2026-07-11 Role/Technical design

이번 검토는 제품 적합성, 구현 가능성, 문서 일관성을 독립적으로 확인했다. 결과적으로 제품 방향은 유지하되 문서 책임, 상태·API 계약, 평가 corpus, Agent 가치 검증과 중단 기준을 다시 정렬했다.

## 1. 유지한 방향

- 실제 개발 진행을 track, work, dependency, milestone과 event로 모델링
- evidence completeness와 decision readiness 분리
- 데이터 부족 시 가역성, downside, detectability, mitigation을 함께 검토
- Role Agent와 Chair의 hidden outcome 접근 차단
- simulated decision과 실제 회사 승인 분리
- deterministic Outcome Engine과 Process/Outcome 평가 분리
- 한국어 Decision Workspace와 progressive disclosure
- 집에서는 synthetic fixture만 사용하고 Atlassian 연동은 사내에서 별도 진행
- 기존 `E:\56_Codex_SoC_Operational_Ontology`의 자동 승계 금지

## 2. 발견하고 수정한 P0

|발견사항|위험|수정|
|---|---|---|
|`PROJECT_PLAN`이 Draft이면서 readiness는 구현 승인|현재 상태와 다음 작업이 다름|Product Plan v0.2로 다시 작성하고 I0만 현재 작업으로 고정|
|제품·기술·실행·reference가 한 문서에 혼합|같은 결정을 여러 문서에서 수정|문서별 decision ownership과 `PLAN_INDEX` 추가|
|Phase, Step, Tech Step, I 단계가 병존|구현 순서를 다르게 해석|I0~I7만 canonical, P0/P1은 issue priority로 정의|
|첫 사용자와 workflow가 미정인 동시에 확정으로 표시|UI와 평가 대상이 흔들림|로컬 design persona와 CASE-VR-001을 고정하고 사내에서 검증할 가설로 분리|
|Case 수가 5, 8, 12~20으로 다름|gate와 fixture 작업량 불명확|첫 release 8개로 고정, 12~20은 I7 이후|
|Decision status와 결론 type 혼합|잘못된 state machine과 API|`DecisionCaseStatus`, `DecisionType`, `AgentRunStatus`, `WorkspacePhase` 분리|
|평가만 소문자 decision synonym 사용|fixture와 validator 불일치|canonical uppercase `DecisionType`으로 통일|
|API가 `/decisions`, `/decision-cases`, `/agent-runs`, `/runs`로 분산|Frontend client와 runbook 불일치|`/api/v1/decision-cases`와 `/api/v1/runs`로 고정|
|시뮬레이션 step과 wall-clock valid time 혼합|미래 정보 leakage와 replay 차이|local field를 `*_at_step`으로 통일, `recorded_at`은 audit 전용|
|Agent가 raw repository에서 무엇을 읽는지 불명확|hidden leakage와 결과 재현 실패|deterministic `ObservableCasePacket` contract 추가|
|5 Role, Challenger, revision, Chair가 9-call budget과 모순|정상 topology도 policy 위반|logical call과 provider attempt를 분리하고 revision 최대 2개로 제한|
|Role Agent가 필요하다는 가정을 검증하지 않음|복잡한 multi-agent 자체가 목표가 됨|B0~B3 ablation과 single-agent/deterministic 축소 기준 추가|

## 3. 발견하고 수정한 P1

|발견사항|수정|
|---|---|
|Replay 회귀와 live Agent 품질을 같은 gate로 해석|Replay는 software regression, live는 grounding/stability/ablation으로 분리|
|한 사람이 작성한 holdout을 일반화 증거로 표현|`sealed unseen`으로 낮추고 로컬 일반화 주장 금지|
|claim 전체에 전역 source list만 연결|atomic claim에 epistemic status, source, inference basis를 연결|
|`case_version`이 fixture, concurrency, projection 의미로 재사용|명확한 version vocabulary 추가|
|Worker recovery 요구는 있으나 lease 계약 없음|PostgreSQL `SKIP LOCKED` lease와 crash/race test 정의|
|root와 Backend에 `pyproject.toml` 위치가 다름|root package 하나와 `backend/src` source로 고정|
|사용성 질문이 I3에서 Agent/Outcome까지 요구|I3 deterministic 질문과 I7 전체 질문으로 gate 분리|
|Business metric 이름만 있고 시작·종료·분모가 없음|C1 metric의 event pair와 집계 방식 추가|
|모든 gate가 기능 추가만 허용|GO, ITERATE, SIMPLIFY, STOP 판정 추가|

## 4. 새 제품 판단

Role Agent는 필요할 가능성이 높지만 무조건 필요한 것은 아니다. 실제 개발 관점의 차이를 만드는지 deterministic core와 single-agent 대비 측정해야 한다.

```text
if multi-role adds validated concern/safeguard:
  keep routed roles
elif single-role adds value:
  simplify to one reviewer
else:
  keep deterministic core + human checklist
```

이 기준은 과거 구현에 다시 끌려가거나 Agent 수를 성과로 착각하는 것을 막는다.

## 5. 남은 한계

- 실제 회사 사용자와 workflow baseline을 아직 검증하지 못함
- sealed unseen corpus도 독립 domain reviewer가 만든 진정한 holdout은 아님
- live model availability와 비용은 I7 실행 시 다시 확인해야 함
- 회사의 Atlassian 형태, 인증, deployment와 model policy가 미정
- 현재 repository에는 계획 문서만 있으며 제품 scaffold는 아직 없음

이 한계는 I0을 막지 않는다. 사내 적용과 business value 주장은 C0/C1을 통과하기 전까지 막는다.

## 6. 최종 판정

- **GO**: I0 repository and quality scaffold
- **KEEP LOCAL**: synthetic fixture, ReplayProvider, simulated Chair/Outcome
- **CONDITIONAL**: multi-role topology, ablation 통과 시 유지
- **NO-GO**: 사내 connector, 실제 승인, write-back, business-value 주장
