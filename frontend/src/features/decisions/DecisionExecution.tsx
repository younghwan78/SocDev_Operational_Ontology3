import type { DecisionWorkspace } from "../../api/generated";

export function DecisionExecution({ item }: { item: DecisionWorkspace }) {
  const plan = item.controls.action_plan;
  if (!plan) return null;
  const outcome = item.outcome_and_evaluation;
  const evidenceRequired = plan.evidence_required_ko ?? [];
  const questionsToResolve = plan.questions_to_resolve_ko ?? [];
  const observedChanges = item.observed_decision_transitions.state_changes ?? [];
  const residualRisks = item.current_brief.residual_risks_ko ?? [];
  const expectedResults = outcome.expected_ko ?? [];
  const actualResults = outcome.actual_ko ?? [];
  const guardrailResults = outcome.guardrail_results_ko ?? [];
  const lessons = outcome.lessons_ko ?? [];

  return (
    <section className="panel execution-panel" id="execution" aria-labelledby="execution-title" tabIndex={-1}>
      <header className="execution-header">
        <div>
          <p className="section-kicker">판단 이후 실행</p>
          <h2 id="execution-title">판단에서 실행과 확인까지 한 흐름으로 봅니다</h2>
        </div>
        <span className={`execution-status ${plan.status}`}>{plan.status_ko}</span>
      </header>

      <section className="decision-record" aria-labelledby="decision-record-title">
        <p className="knowledge-label observed">가상 판단</p>
        <h3 id="decision-record-title">{plan.decision_type_ko}{plan.selected_option_title ? ` · ${plan.selected_option_title}` : ""}</h3>
        <p>{plan.decision_rationale_ko}</p>
      </section>

      <div className="execution-flow" aria-label="원인부터 보호 조치까지의 연결">
        <FlowStep label="원인·판단 근거" value={plan.decision_rationale_ko} />
        <FlowStep label="다음 행동" value={plan.action_ko} />
        <FlowStep
          label="안전 조건"
          value={item.controls.safeguards.length > 0 ? item.controls.safeguards.map((guard) => `${guard.metric_label_ko} ${guard.operator_ko} ${guard.threshold_ko}`).join(" · ") : "별도 실행형 보호 기준 없음"}
        />
        <FlowStep label="실패 시" value={plan.fallback_action_ko} />
      </div>

      <div className="action-safety-grid">
        <article className="action-plan-card">
          <p className="section-kicker">다음 행동</p>
          <h3>{plan.action_ko}</h3>
          <dl>
            <div><dt>담당</dt><dd>{plan.owner}</dd></div>
            <div><dt>기한</dt><dd>Step {plan.due_at_step}</dd></div>
            <div><dt>시작 조건</dt><dd>{plan.trigger_ko}</dd></div>
            <div><dt>확인 방법</dt><dd>{plan.verification_ko}</dd></div>
            <div><dt>실패 시</dt><dd>{plan.fallback_action_ko}</dd></div>
          </dl>
          {evidenceRequired.length > 0 ? <p><strong>필요 근거:</strong> {evidenceRequired.join(", ")}</p> : null}
          {plan.escalation_target_ko ? <p><strong>상위 검토:</strong> {plan.escalation_target_ko}</p> : null}
          {questionsToResolve.length > 0 ? <p><strong>해결 질문:</strong> {questionsToResolve.join(", ")}</p> : null}
          {plan.reopen_condition_ko ? <p><strong>다시 열 조건:</strong> {plan.reopen_condition_ko}</p> : null}
        </article>

        <section className="safeguard-stack" aria-labelledby="safeguard-title">
          <p className="section-kicker">위험 제한</p>
          <h3 id="safeguard-title">안전 조건과 되돌리기(Rollback)</h3>
          {item.controls.safeguards.length > 0 ? item.controls.safeguards.map((guard) => (
            <article className="execution-safeguard" key={guard.safeguard_id}>
              <h4>{guard.metric_label_ko} {guard.operator_ko} {guard.threshold_ko}</h4>
              <p><strong>확인:</strong> Step {guard.check_at_step} · {guard.verification_ko}</p>
              <p><strong>적용 조건:</strong> {guard.condition_ko}</p>
              <p><strong>중단·복구:</strong> {guard.rollback_trigger_ko}</p>
              <p><strong>조치·담당:</strong> {guard.violation_action_ko} · {guard.owner}</p>
              <p><strong>재검토:</strong> Step {guard.expires_at_step}</p>
            </article>
          )) : <p className="empty-copy">이 판단에는 별도 실행형 보호 기준이 없습니다. 다음 행동의 실패 시 조치를 따릅니다.</p>}
        </section>
      </div>

      <section className="observed-progress" aria-labelledby="observed-progress-title">
        <div>
          <p className="section-kicker">관측된 진행</p>
          <h3 id="observed-progress-title">결정이 만든 실제 상태 변화</h3>
        </div>
        {item.observed_decision_transitions.available ? (
          <ul>{observedChanges.map((change) => (
            <li key={`${change.entity_type}-${change.entity_id}`}>
              <span>{entityLabel(change.entity_type)}</span>
              <strong>{change.entity_title}</strong>
              <p>{transitionStateLabel(change.from_state)} → {transitionStateLabel(change.to_state)}</p>
            </li>
          ))}</ul>
        ) : <p>아직 결정 이후 이벤트로 확인된 변화가 없습니다.</p>}
      </section>

      <section className="residual-risk" aria-labelledby="residual-risk-title">
        <h3 id="residual-risk-title">아직 남는 위험</h3>
        {residualRisks.length > 0 ? <ul>{residualRisks.map((risk) => <li key={risk}>{risk}</li>)}</ul> : <p>현재 화면 데이터에 등록된 잔여 위험 없음</p>}
      </section>

      {outcome.outcome_state === "running" ? (
        <section className="outcome-waiting" aria-labelledby="outcome-waiting-title">
          <h3 id="outcome-waiting-title">결과는 다음 Simulation Step 전까지 숨겨집니다</h3>
          <p>현재는 행동, 보호 기준과 확인 시점만 사용합니다. 사후 결과를 미리 판단 근거에 섞지 않습니다.</p>
        </section>
      ) : null}

      {outcome.outcome_state === "available" ? (
        <section className="outcome-comparison" id="outcome" aria-labelledby="outcome-title" tabIndex={-1}>
          <header>
            <p className="section-kicker">결과와 학습</p>
            <h3 id="outcome-title">예상과 실제를 분리해서 비교합니다</h3>
          </header>
          <div className="expectation-actual-grid">
            <article className="expected-result-card"><h4>예상</h4><ResultList items={expectedResults} empty="선택지에 연결된 예상 모델 없음" /></article>
            <article className="actual-result-card"><h4>실제</h4><ResultList items={actualResults} empty="공개된 실제 결과 없음" /></article>
          </div>
          <div className="guardrail-results"><h4>보호 조치 결과</h4><ResultList items={guardrailResults} empty="확인된 보호 기준 결과 없음" /></div>

          {outcome.process_evaluation_ko || outcome.outcome_evaluation_ko ? (
            <div className="evaluation-grid">
              <article><p className="section-kicker">과정 품질</p><h4>당시 판단은 적절했는가</h4><p>{outcome.process_evaluation_ko ?? "아직 평가되지 않았습니다."}</p></article>
              <article><p className="section-kicker">결과 품질</p><h4>위험을 실제로 제한했는가</h4><p>{outcome.outcome_evaluation_ko ?? "아직 평가되지 않았습니다."}</p></article>
            </div>
          ) : null}
          <section className="learning-summary" id="learning" tabIndex={-1}>
            <h4>다음 판단에 남길 학습</h4>
            <ResultList
              items={lessons}
              empty="이번 fixture 결과에 기록된 추가 학습은 없습니다."
            />
          </section>
        </section>
      ) : null}
    </section>
  );
}

function FlowStep({ label, value }: { label: string; value: string }) {
  return <article><span>{label}</span><p>{value}</p></article>;
}

function ResultList({ items, empty }: { items: string[]; empty: string }) {
  return items.length > 0 ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{empty}</p>;
}

function entityLabel(type: "action" | "work_item" | "milestone" | "evidence") {
  return ({ action: "행동", work_item: "작업", milestone: "기준점", evidence: "근거" } as const)[type];
}

function transitionStateLabel(state: string) {
  return ({
    PLANNED: "계획됨",
    READY: "시작 가능",
    IN_PROGRESS: "진행 중",
    BLOCKED: "대기 중",
    COMPLETED: "완료",
    DONE: "완료",
    VERIFIED: "검증 완료",
    REWORK: "재작업",
    CANCELLED: "취소됨",
  } as Record<string, string>)[state] ?? state;
}
