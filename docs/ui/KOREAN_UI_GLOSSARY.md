# 한국어 Decision Workspace 용어 기준

> 상태: UX-A contract + UX-G presentation guidance
> 기준일: 2026-07-19
> 실행 label source: `../../fixtures/dictionaries/labels.ko.yaml`

## 1. 원칙

- 화면의 주어는 Project나 Agent가 아니라 결정 질문이다.
- Backend enum과 ID는 변경하지 않고 한국어 label을 presentation에서 적용한다.
- ISP, RTL, KPI, BW처럼 현업에서 통용되는 약어만 유지한다.
- `가상 판단`, `가상 결과`, `Synthetic fixture` 경계를 항상 표시한다.
- 상태는 색상만이 아니라 원인과 다음 행동을 함께 표시한다.
- `신뢰도 96%`와 같은 단일 숫자 대신 근거·가역성·탐지·복구·잔여 위험을 분리한다.

## 2. Development Twin 지식 상태

|Machine label|사용자 label|의미|
|---|---|---|
|`observed`|관측된 상태|선택 Step까지 observable event로 재구성된 상태|
|`expected_model`|예상 상태 변화|observable claim과 명시적 rule로 계산한 예상|
|`unknown`|현재 모델로 알 수 없음|근거 또는 영향 model이 없어 예측하지 않는 항목|
|`hidden_until_step_advance`|아직 공개되지 않은 결과|simulation advance 전에는 값 자체를 표시하지 않는 outcome|

`예상`을 `예정`이나 `확정`으로 바꾸지 않는다. 과거 Step 화면에는 이후 evidence,
Agent 결과, decision과 hidden outcome을 표시하지 않는다.

## 3. Primary action

|WorkspacePhase|화면 label|
|---|---|
|`CONTEXT_PREPARATION`|상황 구성|
|`READY_FOR_REVIEW`|가상 역할 검토 실행|
|`REVIEW_RUNNING`|진행 상태 보기|
|`DOSSIER_READY`|의견 종합 보기|
|`DECISION_REQUIRED`|가상 최종 판단 실행|
|`OUTCOME_RUNNING`|다음 Simulation Step 진행|
|`EVALUATION_READY`|판단 평가 보기|
|`CLOSED`|학습 요약 보기|

화면에는 현재 phase의 primary action 하나만 강조한다. stale이면 phase action 대신
`최신 상태 불러오기`를 사용한다.

## 4. 피해야 할 표현

|피할 표현|사용할 표현|
|---|---|
|준비도 82점|M2 Freeze까지 1 Step, HW 작업 대기|
|Agent 신뢰도 96%|근거 부분적, 핵심 이견 1개, 잔여 위험 설명|
|Risk 높음|실패 원인, 영향, guardrail, rollback trigger|
|보류|어떤 조건 또는 Step까지 연기|
|No data|아직 실행하지 않은 작업과 다음 행동|
|Ontology node ID|결정과 직접 연결된 영향 경로의 사용자 문장|

## 5. 동기화 규칙

`fixtures/dictionaries/labels.ko.yaml`, `WorkspacePhaseContent`, canonical primary-action
표와 이 문서는 같은 의미를 가져야 한다. UX-A test는 모든 phase가 한 번씩 존재하고
action ID와 한국어 label이 일치하는지 검증한다.

## 6. UX-G 한국어 우선 표현

- `Synthetic fixture`는 일반 화면에서 `합성 데이터`로 표시한다.
- 설명 heading은 `개발 진행 트윈`, `판단 조건`, `역할별 관점`처럼 한국어를 먼저 쓴다.
- 처음 의미 확인이 필요한 핵심 용어는 `선택 가능 기한(Commitment Window)`,
  `되돌리기(Rollback)`처럼 한국어 뒤에 원어를 병기할 수 있다.
- `Guardrail`은 문맥상 `보호 기준` 또는 `안전 조건`으로, `Blocker`는 `대기 원인`으로,
  `Milestone`은 `기준점`으로 표시한다.
- `Simulation Step`은 canonical primary-action label이므로 UX-G에서 변경하지 않는다.
- 실제 팀명, 제품명, ISP/RTL/BW와 같은 현업 약어는 번역하지 않는다.
- API/provider error, option ID와 ontology ID는 URL과 일반 화면에 노출하지 않는다.
