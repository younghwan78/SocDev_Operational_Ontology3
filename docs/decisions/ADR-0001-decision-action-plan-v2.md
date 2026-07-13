# ADR-0001: 모든 모의 결정에 실행 가능한 다음 행동을 포함한다

> 상태: Accepted
> 날짜: 2026-07-14
> 범위: local fixture-only PoC, I7 usability hardening

## 맥락

`simulated-decision.v1`은 결정 유형, 근거, dissent, 조건부 안전장치를 기록했지만,
`COLLECT_MINIMUM_EVIDENCE`, `DEFER_UNTIL_TRIGGER`, `ESCALATE`, `REJECT` 이후 누가
무엇을 언제까지 하고 어떻게 확인할지는 공통 계약으로 표현하지 않았다. 이 상태에서는
데이터 부족을 말하는 조언이 실제 개발 의사결정의 다음 단계로 이어지지 않을 수 있다.

## 결정

`SimulatedDecision`을 `simulated-decision.v2`로 올리고 모든 결정에 정확히 하나의
`decision-action-plan.v1`을 필수로 둔다.

공통 필드는 다음과 같다.

- `action_type`: `execute`, `collect_evidence`, `defer`, `escalate`, `reject`
- `owner`: 다음 행동의 책임 역할
- `action`: 수행할 구체적 행동
- `due_at_step`: wall-clock이 아닌 canonical simulation step 기한
- `trigger`: 행동 또는 재검토를 시작하는 조건
- `verification`: 완료 확인 방법
- `fallback_action`: 기한 또는 행동 실패 시 조치

결정 유형별 추가 규칙은 다음과 같다.

|DecisionType|필수 action type|추가 필수 항목|
|---|---|---|
|`APPROVE`|`execute`|없음|
|`APPROVE_WITH_GUARDRAILS`|`execute`|기존 `Safeguard` 계약|
|`RUN_REVERSIBLE_TRIAL`|`execute`|기존 `Safeguard` 계약|
|`COLLECT_MINIMUM_EVIDENCE`|`collect_evidence`|`evidence_required` 1개 이상|
|`DEFER_UNTIL_TRIGGER`|`defer`|공통 trigger와 기한|
|`ESCALATE`|`escalate`|`escalation_target`, `questions_to_resolve`|
|`REJECT`|`reject`|`reopen_condition`|

데이터가 부족하다는 이유만으로 `ESCALATE`하지 않는다. 현재 역할의 권한 범위 또는
비가역 위험 통제 범위를 넘을 때만 상신하고, 상신 대상·해결 질문·기한·fallback을
함께 기록한다. 최종 승인은 여전히 사람이 수행하며, 로컬 PoC의 Chair는
`simulated=true`인 비권위적 판단만 만든다.

## Agent와 deterministic core 적용

- Replay/deterministic Chair는 같은 action-plan builder를 사용한다.
- OpenAI/Codex CLI Chair는 동일한 Pydantic JSON Schema로 응답한다.
- `prompts.v2`는 데이터 부족 시 risk-limiting trade-off를 유지하면서 결정 유형별
  실행 필드를 명시하도록 요구한다.
- runtime validator는 `due_at_step`이 packet의 `current_step`보다 과거이면 거부한다.
- Agent는 계속 검증된 `ObservableCasePacket`만 받으며 hidden fixture에는 접근하지 않는다.

## 호환성과 저장 데이터

필수 필드 추가이므로 같은 major에 넣지 않고 v2로 변경한다. Alembic
`0017_decision_action_plan_v2`가 다음 JSONB 위치의 v1 결정을 v2로 변환한다.

- `observable.simulated_decisions.payload.decision`
- `observable.agent_run_steps.normalized_output.decision`
- `observable.agent_runs.result.chair_provider_result.decision`
- `hidden.outcome_evaluations.payload.ablation.decision`

기존 결정은 실행 권한을 확대하지 않는 `재검토` action plan을 받는다. downgrade는
`action_plan`을 제거하고 v1 schema version을 복원하므로, 운영 데이터에 적용하기 전
백업이 필요하다.

기존 `eval-2026-07-11.1`과 `prompts.v1`은 변경하지 않는다. 같은 8개 fixture에 새
계약과 prompt hash를 고정한 `eval-2026-07-14.1`을 개발 회귀 기준으로 추가한다.
이 release는 새로운 sealed-unseen corpus를 뜻하지 않으며, 기존 sealed 정보가
변경에 사용되었다면 별도 corpus release가 필요하다.

## 결과

장점은 UI와 평가가 결정문을 읽고 다음 행동을 추론하지 않아도 된다는 점이다. 반면
계약과 prompt가 더 엄격해져 live provider의 structured output 실패 가능성이 커지므로,
Step 1에서는 Replay 회귀를 통과시키고 live 안정성 판정은 기존 I7 외부-input gate로
남긴다.
