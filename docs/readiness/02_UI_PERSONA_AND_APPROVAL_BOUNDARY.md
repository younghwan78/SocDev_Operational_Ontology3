# UI persona and approval boundary

> Status: APPROVED  
> Date: 2026-07-16
> Detailed interaction and information design: `../../internal_docs/26.07.16 결정 중심 UX 설계.md`

## 1. Primary persona

The MVP primary user is:

> **Multimedia System/Architecture Reviewer**

Primary responsibilities:

- understand current cross-track development state
- compare architecture/implementation alternatives
- identify blockers, uncertainty, and irreversible choices
- review Role Agent agreement and dissent
- understand the simulated Chair decision and safeguards

The UI is optimized for this persona, not for every stakeholder equally.

## 2. Secondary persona

`Technical PM/Reviewer` is the secondary persona.

Secondary needs:

- decision deadline
- blocking dependency
- owner and next action
- milestone impact
- residual risk and escalation

These needs appear in the same Decision Workspace. A separate PM dashboard is out of scope.

## 3. Developer persona

`Fixture/Agent Developer` uses `/dev/fixtures` and CLI tools for:

- contract validation
- fixture freeze
- observable/hidden leakage test
- prompt/model/run trace
- evaluation detail

Developer controls must not appear in normal user navigation.

## 4. Home approval boundary

```text
User:
  approves product contract and freezes fixture/evaluation definitions

World Builder/Fixture Auditor:
  proposes and audits synthetic cases

Runtime Role Agents:
  analyze observable state

Decision Chair:
  produces simulated_decision

Outcome Engine:
  produces simulated_outcome

Evaluator:
  scores process and outcome
```

During an evaluation run the user cannot edit Role reviews, Chair decision, hidden outcome, or expected result. Otherwise the evaluation would no longer be reproducible.

The user may discard a run and create a new run with a new configuration. The prior run remains immutable.

## 5. Future company boundary

In a company pilot:

- Decision Chair output becomes a recommendation.
- A named human authority records the final decision.
- Write-back requires explicit human approval.
- Human modification/rejection reason becomes evaluation data.

This future boundary is not implemented at home.

## 6. User workflow

```text
Decision List
  → open Decision Workspace
  → inspect situation and progress
  → run or replay virtual review
  → inspect agreement/dissent
  → run simulated Chair
  → inspect safeguards and residual risk
  → advance outcome
  → compare process and outcome evaluation
```

## 7. Primary action by workspace phase

`WorkspacePhase` is a derived read-model field, not `DecisionCaseStatus`. Canonical values are defined in `08_CANONICAL_TERMS_AND_API_CONTRACT.md`.

|Workspace phase|Primary action|
|---|---|
|CONTEXT_PREPARATION|상황 구성|
|READY_FOR_REVIEW|가상 역할 검토 실행|
|REVIEW_RUNNING|진행 상태 보기|
|DOSSIER_READY|의견 종합 보기|
|DECISION_REQUIRED|가상 최종 판단 실행|
|OUTCOME_RUNNING|다음 Simulation Step 진행|
|EVALUATION_READY|판단 평가 보기|
|CLOSED|학습 요약 보기|

Only one primary action is emphasized at a time.

## 8. Information priority

Default view order:

1. decision question and deadline
2. one-line recommendation or current state
3. development state at the selected step, causal blocker propagation, and next commitment window
4. alternative comparison
5. role agreement/dissent
6. guardrail, rollback trigger, next action
7. evidence, assumptions, timeline, raw detail

## 9. Technical detail policy

- Raw IDs are hidden by default.
- Full role outputs are collapsed.
- Ontology graph is developer detail.
- Source fact and assumption are visually distinct.
- `가상 판단` and `가상 결과` are always visible.
- Risk is shown with cause and action, not color alone.

## 10. Usability acceptance

Use a frozen CASE-VR-001 task script, start state, allowed-screen list, and answer rubric. Store evidence in `output/usability/<run-id>/report.md`.

At I3, the primary user must answer questions 1 through 4 without raw JSON or an ontology graph:

1. What must be decided?
2. When is the decision needed?
3. Which development track is blocked?
4. Which alternative is reversible?
5. Where do agents disagree?
6. What guardrail and rollback trigger apply?
7. What residual risk did the Chair accept?
8. Why can process quality differ from outcome quality?

At I7, the user must answer all eight questions. The report records pass/fail per question, wrong primary-action clicks, whether raw detail was opened, elapsed task time, and reviewer notes. Failure on an applicable question blocks that stage's usability gate.

## 11. Post-I7 Development Twin UX acceptance

The post-I7 UX redesign adds a supplemental gate without changing the historical I3/I7 result. The primary user must also answer:

1. At a selected simulation step, what are the states of the critical development tracks and WorkItems?
2. Which DevelopmentEvent caused the blocker, and how did the impact propagate to downstream work and milestones?
3. Which commitment window closes next, and what option or switching-cost advantage is lost afterward?
4. What state transitions are expected for each alternative, and which impacts remain unknown?
5. After a decision and action advance, which WorkItem, milestone, evidence, and action states actually changed?

The user must distinguish `observed state`, `expected transition from the observable model`, and `hidden outcome not yet revealed`. A past-step view must not expose later evidence, decisions, Agent output, or hidden outcome. These checks are required by the UX redesign gate and do not retroactively invalidate the completed I7 Replay gate.
