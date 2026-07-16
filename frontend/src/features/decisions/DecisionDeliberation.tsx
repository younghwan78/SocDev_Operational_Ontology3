import type { DecisionWorkspace } from "../../api/generated";

type Deliberation = DecisionWorkspace["deliberation"];
type EpistemicItem = NonNullable<Deliberation["epistemic_items"]>[number];

const EPISTEMIC_GROUPS = [
  { key: "fact", label: "확인된 사실", description: "출처와 관측 시점을 확인할 수 있습니다." },
  { key: "inference", label: "근거 기반 추론", description: "관측 source와 등록된 추론 규칙을 구분합니다." },
  { key: "assumption", label: "검토할 가정", description: "담당 또는 재검토 Step이 있는 가정입니다." },
  { key: "unknown", label: "아직 모름", description: "왜 모르며 언제 확인 가능한지 표시합니다." },
] as const;

export function DecisionDeliberation({ deliberation }: { deliberation: Deliberation }) {
  const epistemicItems = deliberation.epistemic_items ?? [];
  return (
    <section className="deliberation-section" aria-labelledby="deliberation-title">
      <header className="deliberation-header">
        <p className="section-kicker">쟁점과 불확실성</p>
        <h2 id="deliberation-title">Role이 어디서 일치하고 충돌하는가</h2>
        <p>Role별 긴 답변보다 일치, 핵심 이견과 확인 필요를 먼저 보여줍니다.</p>
      </header>

      {deliberation.alignment_available ? (
        <>
          <div className="alignment-grid">
            <section className="alignment-card agreement" aria-labelledby="agreement-title">
              <h3 id="agreement-title">의견 일치</h3>
              {(deliberation.agreement_groups ?? []).length > 0 ? (
                <ul>{(deliberation.agreement_groups ?? []).map((group) => <li key={`${group.recommendation}-${group.summary_ko}`}><strong>{group.recommendation_ko}</strong><span>{group.summary_ko}</span></li>)}</ul>
              ) : <p>확인된 일치 그룹 없음</p>}
            </section>
            <section className="alignment-card dissent" aria-labelledby="dissent-title">
              <h3 id="dissent-title">핵심 이견</h3>
              {(deliberation.dissent_items ?? []).length > 0 ? (
                <ul>{(deliberation.dissent_items ?? []).map((item) => <li key={`${item.role_label_ko}-${item.recommendation}`}><strong>{item.role_label_ko} · {item.recommendation_ko}</strong><span>{item.rationale_ko}</span></li>)}</ul>
              ) : <p>기록된 핵심 이견 없음</p>}
            </section>
            <section className="alignment-card confirmation" aria-labelledby="confirmation-title">
              <h3 id="confirmation-title">확인 필요</h3>
              {deliberation.needs_confirmation_ko.length > 0 ? <ul>{deliberation.needs_confirmation_ko.map((item) => <li key={item}>{item}</li>)}</ul> : <p>추가 확인 항목 없음</p>}
            </section>
          </div>

          {(deliberation.challenge_changes ?? []).length > 0 ? (
            <section className="challenge-changes" aria-labelledby="challenge-change-title">
              <h3 id="challenge-change-title">반론 후 변경</h3>
              <ul>{(deliberation.challenge_changes ?? []).map((change) => <li key={`${change.role_label_ko}-${change.summary_ko}`}><strong>{change.role_label_ko}</strong><span>{change.before_recommendation_ko} → {change.after_recommendation_ko}</span><p>{change.summary_ko}</p></li>)}</ul>
            </section>
          ) : null}

          <details className="role-originals">
            <summary>Role별 원문 보기</summary>
            <p className="detail-explanation">권고를 검증할 때만 펼치세요. provider, token과 실행 trace는 일반 사용자 화면에 표시하지 않습니다.</p>
            <div className="role-review-list">
              {(deliberation.role_reviews ?? []).map((review) => (
                <article className="role-review-detail" key={review.role_label_ko}>
                  <p className="section-kicker">{review.role_label_ko}</p>
                  <h3>{review.recommendation_ko}{review.recommended_option_title ? ` · ${review.recommended_option_title}` : ""}</h3>
                  <p>{review.rationale_ko}</p>
                  {review.unique_concern_ko ? <p><strong>고유 concern:</strong> {review.unique_concern_ko}</p> : null}
                  {(review.risks_ko ?? []).length > 0 ? <><h4>위험과 대응</h4><ul>{(review.risks_ko ?? []).map((risk) => <li key={risk}>{risk}</li>)}</ul></> : null}
                  {(review.information_gaps_ko ?? []).length > 0 ? <><h4>정보 공백</h4><ul>{(review.information_gaps_ko ?? []).map((gap) => <li key={gap}>{gap}</li>)}</ul></> : null}
                  <p className="qualitative-confidence">정성적 확신 수준: {review.confidence_ko}</p>
                  {review.revision ? <div className="role-revision"><strong>반론 후 보강</strong><p>{review.revision.recommendation_ko} · {review.revision.rationale_ko}</p></div> : null}
                </article>
              ))}
            </div>
          </details>
        </>
      ) : (
        <section className="alignment-empty">
          <h3>아직 Role 의견 종합이 없습니다</h3>
          <p>다중 역할 검토가 완료되면 일치, 핵심 이견과 확인 필요를 이 위치에서 비교합니다.</p>
        </section>
      )}

      <section className="epistemic-section" aria-labelledby="epistemic-title">
        <div className="epistemic-heading">
          <h3 id="epistemic-title">사실·추론·가정·미확인</h3>
          <p>정밀한 confidence 숫자 대신 지식의 종류와 확인 경계를 표시합니다.</p>
        </div>
        <div className="epistemic-grid">
          {EPISTEMIC_GROUPS.map((group) => {
            const items = epistemicItems.filter((item) => item.epistemic_status === group.key);
            return <EpistemicGroup group={group} items={items} key={group.key} />;
          })}
        </div>
      </section>
    </section>
  );
}

function EpistemicGroup({ group, items }: { group: typeof EPISTEMIC_GROUPS[number]; items: EpistemicItem[] }) {
  const primaryItems = items.slice(0, 2);
  const additionalItems = items.slice(2);
  return (
    <section className="epistemic-group" data-epistemic={group.key}>
      <header><span className="epistemic-dot" aria-hidden="true" /><div><h4>{group.label}</h4><p>{group.description}</p></div></header>
      {primaryItems.length > 0 ? primaryItems.map((item) => <EpistemicCard item={item} key={`${item.epistemic_status}-${item.statement_ko}`} />) : <p className="comparison-empty">현재 표시할 항목 없음</p>}
      {additionalItems.length > 0 ? <details><summary>추가 {additionalItems.length}개 보기</summary>{additionalItems.map((item) => <EpistemicCard item={item} key={`${item.epistemic_status}-${item.statement_ko}`} />)}</details> : null}
    </section>
  );
}

function EpistemicCard({ item }: { item: EpistemicItem }) {
  return (
    <article className="epistemic-card">
      <p>{item.statement_ko}</p>
      {(item.source_titles_ko ?? []).length > 0 ? <small>출처: {(item.source_titles_ko ?? []).join(", ")}{item.observed_at_step !== null && item.observed_at_step !== undefined ? ` · Step ${item.observed_at_step} 관측` : ""}</small> : null}
      {(item.inference_basis_ko ?? []).length > 0 ? <small>{(item.inference_basis_ko ?? []).join(" ")}</small> : null}
      {item.owner_ko ? <small>담당: {item.owner_ko}{item.expires_at_step !== null && item.expires_at_step !== undefined ? ` · Step ${item.expires_at_step} 재검토` : ""}</small> : null}
      {item.unknown_reason_ko ? <small>{item.unknown_reason_ko}{item.expected_confirmation_step !== null && item.expected_confirmation_step !== undefined ? ` Step ${item.expected_confirmation_step}에 다시 확인합니다.` : ""}</small> : null}
    </article>
  );
}
