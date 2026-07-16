import { useState } from "react";

import type { DecisionWorkspace } from "../../api/generated";

type Alternatives = DecisionWorkspace["alternatives"];
type Alternative = Alternatives["items"][number];

export function AlternativeComparison({ alternatives }: { alternatives: Alternatives }) {
  const [mobileIndex, setMobileIndex] = useState(0);
  const activeIndex = Math.min(mobileIndex, alternatives.items.length - 1);
  const active = alternatives.items[activeIndex];

  return (
    <section className="panel alternative-comparison" id="alternatives" aria-labelledby="alternatives-title">
      <header className="comparison-header">
        <div>
          <p className="section-kicker">선택지 비교</p>
          <h2 id="alternatives-title">같은 기준으로 선택지를 비교합니다</h2>
        </div>
        <p>전체 점수나 자동 순위 없이 효과, 일정, 실패 영향과 되돌리기 조건을 나란히 봅니다.</p>
      </header>

      <div className="desktop-comparison">
        <table className="option-comparison-table">
          <caption className="sr-only">선택지별 기대 효과, 일정, 실패 영향, 가역성과 근거 비교</caption>
          <thead>
            <tr>
              <th scope="col">선택지</th>
              <th scope="col">기대 효과</th>
              <th scope="col">일정 영향</th>
              <th scope="col">실패 영향</th>
              <th scope="col">되돌리기·비용</th>
              <th scope="col">필요한 근거</th>
              <th scope="col">안전 조건</th>
              <th scope="col">남는 위험</th>
            </tr>
          </thead>
          <tbody>
            {alternatives.items.map((option) => (
              <tr key={option.option_id} data-recommended={option.recommended}>
                <th scope="row"><OptionTitle option={option} /></th>
                <td>{option.expected_effect_ko ?? option.description}</td>
                <td><ComparisonList values={option.schedule_impact_ko} empty="일정 영향 모델 없음" /></td>
                <td><ComparisonList values={option.failure_impact_ko} empty="확인된 실패 영향 없음" /></td>
                <td>{option.reversibility_ko ?? quantityLabel(option.switching_cost)}</td>
                <td><ComparisonList values={option.required_evidence_ko} empty="추가 근거 지정 없음" /></td>
                <td><ComparisonList values={option.safety_conditions_ko} empty="선택지별 조건 미등록" /></td>
                <td><ComparisonList values={option.residual_risks_ko} empty="현재 모델의 잔여 위험 없음" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-comparison">
        <div className="mobile-option-controls" aria-label="모바일 선택지 이동">
          <button type="button" className="secondary-button" disabled={activeIndex === 0} onClick={() => setMobileIndex((current) => Math.max(0, current - 1))}>이전 선택지</button>
          <p>{activeIndex + 1} / {alternatives.items.length}</p>
          <button type="button" className="secondary-button" disabled={activeIndex === alternatives.items.length - 1} onClick={() => setMobileIndex((current) => Math.min(alternatives.items.length - 1, current + 1))}>다음 선택지</button>
        </div>
        <article className="mobile-option-card">
          <OptionTitle option={active} />
          <ComparisonField label="기대 효과" values={[active.expected_effect_ko ?? active.description]} />
          <ComparisonField label="일정 영향" values={active.schedule_impact_ko} empty="일정 영향 모델 없음" />
          <ComparisonField label="실패 영향" values={active.failure_impact_ko} empty="확인된 실패 영향 없음" />
          <ComparisonField label="되돌리기·비용" values={[active.reversibility_ko ?? quantityLabel(active.switching_cost)]} />
          <ComparisonField label="필요한 근거" values={active.required_evidence_ko} empty="추가 근거 지정 없음" />
          <ComparisonField label="안전 조건" values={active.safety_conditions_ko} empty="선택지별 조건 미등록" />
          <ComparisonField label="남는 위험" values={active.residual_risks_ko} empty="현재 모델의 잔여 위험 없음" />
        </article>
      </div>
    </section>
  );
}

function OptionTitle({ option }: { option: Alternative }) {
  return (
    <div className="comparison-option-title">
      {option.recommended ? <span className="recommendation-badge">Role 검토 권고</span> : null}
      <strong>{option.title}</strong>
      {option.recommendation_reason_ko ? <small>{option.recommendation_reason_ko}</small> : null}
    </div>
  );
}

function ComparisonField({ label, values, empty }: { label: string; values: string[] | undefined; empty?: string }) {
  return (
    <div className="mobile-comparison-field">
      <h3>{label}</h3>
      <ComparisonList values={values} empty={empty ?? "등록 내용 없음"} />
    </div>
  );
}

function ComparisonList({ values, empty }: { values: string[] | undefined; empty: string }) {
  const entries = values ?? [];
  if (entries.length === 0) return <span className="comparison-empty">{empty}</span>;
  if (entries.length === 1) return <span>{entries[0]}</span>;
  return <ul>{entries.map((entry) => <li key={entry}>{entry}</li>)}</ul>;
}

function quantityLabel(quantity: Alternative["switching_cost"]) {
  if (quantity.mode === "exact") return `${quantity.value} ${quantity.unit}`;
  if (quantity.mode === "range") return `${quantity.lower_bound}–${quantity.upper_bound} ${quantity.unit}`;
  if (quantity.mode === "qualitative") return `${quantity.qualitative} 수준`;
  return "아직 정량화되지 않음";
}
