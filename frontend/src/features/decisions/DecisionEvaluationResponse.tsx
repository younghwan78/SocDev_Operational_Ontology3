import { useState } from "react";

import type {
  DecisionEvaluationResponse as EvaluationResponse,
  DecisionFinalResponseCommand,
  DecisionWorkspace,
} from "../../api/generated";

type ResponseInput = {
  optionId: string;
  acceptedRisks: string;
  safeguards: string;
  rationale: string;
};

const emptyInput: ResponseInput = {
  optionId: "",
  acceptedRisks: "",
  safeguards: "",
  rationale: "",
};

export function DecisionEvaluationResponse({
  item,
  response,
  pending,
  error,
  onRecordInitial,
  onRevealAdvice,
  onRecordFinal,
}: {
  item: DecisionWorkspace;
  response: EvaluationResponse | null | undefined;
  pending: boolean;
  error: string | null;
  onRecordInitial: (command: {
    option_id: string;
    accepted_risks_ko: string[];
    safeguards_ko: string[];
    rationale_ko: string;
  }) => void;
  onRevealAdvice: () => void;
  onRecordFinal: (
    command: Omit<DecisionFinalResponseCommand, "command_schema_version">,
  ) => void;
}) {
  const [initial, setInitial] = useState<ResponseInput>(emptyInput);
  const [final, setFinal] = useState<ResponseInput>(emptyInput);
  const [adoption, setAdoption] = useState<"accept" | "modify" | "reject">("accept");
  const [differenceReason, setDifferenceReason] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const initialRecord = response?.initial_response;
  const advice = response?.advice_snapshot;
  const finalRecord = response?.final_response;

  const submitInitial = () => {
    const normalized = normalizeInput(initial);
    if (!normalized) {
      setValidationError("선택지, 감수할 위험, 보호 조치와 판단 이유를 모두 입력하세요.");
      return;
    }
    setValidationError(null);
    onRecordInitial(normalized);
  };
  const submitFinal = () => {
    const normalized = normalizeInput(final);
    if (!normalized) {
      setValidationError("사후 선택지, 감수할 위험, 보호 조치와 판단 이유를 모두 입력하세요.");
      return;
    }
    if (adoption !== "accept" && !differenceReason.trim()) {
      setValidationError("수정 또는 거부한 이유를 입력하세요.");
      return;
    }
    setValidationError(null);
    onRecordFinal({
      ...normalized,
      adoption,
      difference_reason_ko: differenceReason.trim() || null,
    });
  };

  return (
    <section
      className="panel evaluation-response-panel"
      id="evaluation-response"
      aria-labelledby="evaluation-response-title"
      tabIndex={-1}
    >
      <header>
        <p className="section-kicker">조언 영향 평가</p>
        <h2 id="evaluation-response-title">내 판단과 가상 조언을 분리해 기록합니다</h2>
        <p>
          이 기능은 로컬 builder의 engineering proxy입니다. 사람 평가, 최종 승인 또는
          사내 시스템 기록으로 사용하지 않습니다.
        </p>
      </header>

      {!initialRecord ? (
        <ResponseForm
          legend="1. 조언을 보기 전 내 판단"
          value={initial}
          onChange={setInitial}
          options={item.alternatives.items}
        >
          <button className="primary-button" type="button" onClick={submitInitial} disabled={pending}>
            {pending ? "사전 판단 기록 중…" : "사전 판단을 변경 불가로 기록"}
          </button>
        </ResponseForm>
      ) : (
        <RecordedResponse
          title="1. 조언 전 판단 · 기록 완료"
          optionTitle={optionTitle(item, initialRecord.option_id)}
          risks={initialRecord.accepted_risks_ko}
          safeguards={initialRecord.safeguards_ko}
          rationale={initialRecord.rationale_ko}
        />
      )}

      {initialRecord && !item.controls.action_plan ? (
        <section className="evaluation-phase" aria-labelledby="advice-preparation-title">
          <p className="evaluation-step">2</p>
          <div>
            <h3 id="advice-preparation-title">가상 조언 준비</h3>
            <p>
              사전 판단은 잠겼습니다. 기존 가상 역할 검토와 최종 판단을 실행한 뒤에도
              조언 내용은 공개 전까지 표시되지 않습니다.
            </p>
          </div>
        </section>
      ) : null}

      {initialRecord && item.controls.action_plan && !advice ? (
        <section className="evaluation-phase" aria-labelledby="advice-reveal-title">
          <p className="evaluation-step">2</p>
          <div>
            <h3 id="advice-reveal-title">가상 조언이 준비되었습니다</h3>
            <p>
              공개 시점이 기록되며 이후에는 조언 전 상태로 돌아갈 수 없습니다.
            </p>
            <button className="primary-button" type="button" onClick={onRevealAdvice} disabled={pending}>
              {pending ? "가상 조언 공개 중…" : "조언 공개 시점 기록"}
            </button>
          </div>
        </section>
      ) : null}

      {advice && !finalRecord ? (
        <>
          <section className="evaluation-phase advice-revealed" aria-labelledby="advice-revealed-title">
            <p className="evaluation-step complete">2</p>
            <div>
              <h3 id="advice-revealed-title">가상 조언 공개 완료</h3>
              <p>
                권고 선택지: <strong>{advice.selected_option_id
                  ? optionTitle(item, advice.selected_option_id)
                  : "특정 선택지 없음"}</strong>
              </p>
              <p>판단 유형: {decisionTypeLabel(advice.decision_type)}</p>
            </div>
          </section>
          <ResponseForm
            legend="3. 조언을 본 뒤 최종 판단"
            value={final}
            onChange={setFinal}
            options={item.alternatives.items}
          >
            <fieldset className="adoption-fieldset">
              <legend>조언 반영 방식</legend>
              {(["accept", "modify", "reject"] as const).map((value) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="advice-adoption"
                    value={value}
                    checked={adoption === value}
                    onChange={() => setAdoption(value)}
                  />
                  {adoptionLabel(value)}
                </label>
              ))}
            </fieldset>
            {adoption !== "accept" ? (
              <label>
                조언과 다르게 판단한 이유
                <textarea
                  name="difference-reason"
                  autoComplete="off"
                  value={differenceReason}
                  onChange={(event) => setDifferenceReason(event.target.value)}
                  placeholder="어떤 근거 또는 위험 때문에 수정하거나 거부했는지 입력…"
                />
              </label>
            ) : null}
            <button className="primary-button" type="button" onClick={submitFinal} disabled={pending}>
              {pending ? "최종 판단 기록 중…" : "최종 판단을 변경 불가로 기록"}
            </button>
          </ResponseForm>
        </>
      ) : null}

      {finalRecord ? (
        <>
          <RecordedResponse
            title={`3. 최종 판단 · ${adoptionLabel(finalRecord.adoption)}`}
            optionTitle={optionTitle(item, finalRecord.option_id)}
            risks={finalRecord.accepted_risks_ko}
            safeguards={finalRecord.safeguards_ko}
            rationale={finalRecord.rationale_ko}
          />
          {finalRecord.difference_reason_ko ? (
            <p><strong>조언과 다른 이유:</strong> {finalRecord.difference_reason_ko}</p>
          ) : null}
          <p className="evaluation-boundary">
            이 응답은 simulated Chair의 판단이나 실행 계획을 변경하지 않습니다.
          </p>
        </>
      ) : null}

      {validationError ? <p className="form-error" role="alert">{validationError}</p> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </section>
  );
}

function ResponseForm({
  legend,
  value,
  onChange,
  options,
  children,
}: {
  legend: string;
  value: ResponseInput;
  onChange: (value: ResponseInput) => void;
  options: DecisionWorkspace["alternatives"]["items"];
  children: React.ReactNode;
}) {
  return (
    <fieldset className="evaluation-response-form">
      <legend>{legend}</legend>
      <label>
        선택지
        <select
          name={`${legend}-option`}
          value={value.optionId}
          onChange={(event) => onChange({ ...value, optionId: event.target.value })}
        >
          <option value="">선택하세요</option>
          {options.map((option) => (
            <option key={option.option_id} value={option.option_id}>{option.title}</option>
          ))}
        </select>
      </label>
      <label>
        감수할 위험
        <textarea
          name={`${legend}-risks`}
          autoComplete="off"
          value={value.acceptedRisks}
          onChange={(event) => onChange({ ...value, acceptedRisks: event.target.value })}
          placeholder="한 줄에 하나씩 입력…"
        />
      </label>
      <label>
        필요한 보호 조치
        <textarea
          name={`${legend}-safeguards`}
          autoComplete="off"
          value={value.safeguards}
          onChange={(event) => onChange({ ...value, safeguards: event.target.value })}
          placeholder="한 줄에 하나씩 입력…"
        />
      </label>
      <label>
        판단 이유
        <textarea
          name={`${legend}-rationale`}
          autoComplete="off"
          value={value.rationale}
          onChange={(event) => onChange({ ...value, rationale: event.target.value })}
          placeholder="현재 근거와 trade-off를 바탕으로 입력…"
        />
      </label>
      {children}
    </fieldset>
  );
}

function RecordedResponse({
  title,
  optionTitle: selectedOption,
  risks,
  safeguards,
  rationale,
}: {
  title: string;
  optionTitle: string;
  risks: string[];
  safeguards: string[];
  rationale: string;
}) {
  return (
    <section className="recorded-response" aria-label={title}>
      <h3>{title}</h3>
      <dl>
        <div><dt>선택</dt><dd>{selectedOption}</dd></div>
        <div><dt>감수할 위험</dt><dd>{risks.join(" · ")}</dd></div>
        <div><dt>보호 조치</dt><dd>{safeguards.join(" · ")}</dd></div>
        <div><dt>판단 이유</dt><dd>{rationale}</dd></div>
      </dl>
    </section>
  );
}

function normalizeInput(value: ResponseInput) {
  const acceptedRisks = splitLines(value.acceptedRisks);
  const safeguards = splitLines(value.safeguards);
  const rationale = value.rationale.trim();
  if (!value.optionId || acceptedRisks.length === 0 || safeguards.length === 0 || !rationale) {
    return null;
  }
  return {
    option_id: value.optionId,
    accepted_risks_ko: acceptedRisks,
    safeguards_ko: safeguards,
    rationale_ko: rationale,
  };
}

function splitLines(value: string) {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function optionTitle(item: DecisionWorkspace, optionId: string) {
  return item.alternatives.items.find((option) => option.option_id === optionId)?.title ?? optionId;
}

function adoptionLabel(value: "accept" | "modify" | "reject") {
  return ({ accept: "수용", modify: "수정", reject: "거부" } as const)[value];
}

function decisionTypeLabel(value: string) {
  return ({
    PROCEED: "진행",
    PROCEED_WITH_SAFEGUARDS: "안전 조건부 진행",
    DEFER: "보류",
    REJECT: "거부",
    REQUEST_MORE_EVIDENCE: "추가 근거 요청",
  } as Record<string, string>)[value] ?? value;
}
