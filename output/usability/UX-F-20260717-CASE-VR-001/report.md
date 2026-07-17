# UX-F frozen CASE-VR-001 task report

> Run ID: `UX-F-20260717-CASE-VR-001`
> Date: 2026-07-17
> Evaluator: local Codex evaluator + deterministic Playwright 1.61.1
> Data/provider: synthetic fixture + ReplayProvider
> Result: **PASS for the local agent-substitute gate**

## 1. Frozen protocol

- Start state: CASE-VR-001, current Step 12, no review run, no simulated decision.
- Allowed screens: `/decisions` and `/decisions/CASE-VR-001` normal user surfaces.
- Disallowed aids: raw JSON, ontology graph, `/dev/fixtures`, hidden fixture, database query,
  Role-original detail for questions 1–6.
- Flow: Inbox → Workspace → B2 virtual review → simulated Chair → Step advance → evaluation.
- Required recovery checks: partial review and aggregate-version conflict/stale refresh.
- A failed applicable question, wrong primary action, raw-detail use for questions 1–6, hidden-outcome
  exposure, or page-level horizontal scroll is a gate failure.

## 2. Canonical eight questions

|No.|Question|Answer obtained from the normal UI|Result|
|---:|---|---|---|
|1|What must be decided?|Whether to proceed with UHD60 EIS under limited conditions before measurement completes.|PASS|
|2|When is the decision needed?|Architecture Freeze at Step 13; the start state has 1 Step remaining.|PASS|
|3|Which development track is blocked?|Architecture is the critical track in the Inbox; its EIS-option decision propagates to the blocked HW/RTL carry-over review and RTL Freeze.|PASS|
|4|Which alternative is reversible?|Both displayed alternatives are reversible; limited progress preserves immediate SW feature-flag rollback at 3 person-days, while deferral costs 3 Steps.|PASS|
|5|Where do agents disagree?|Architecture and SW favor a reversible trial; Verification asks for minimum evidence and Technical PM favors deferral until a trigger. The rationale and unresolved checks are visible before Role originals.|PASS|
|6|What guardrail and rollback trigger apply?|Keep DDR bandwidth within the 20 GB/s guardrail, verify at Step 15, and stop/rollback or re-review when the agreed range is exceeded or the blocker grows.|PASS|
|7|What residual risk did the Chair accept?|Actual DDR bandwidth under sustained thermal conditions remains unknown.|PASS|
|8|Why can process quality differ from outcome quality?|Process quality asks whether the decision used the then-available dependencies, dissent, safeguards, and next action; outcome quality asks whether later risk signals were actually limited by the protection action.|PASS|

## 3. Development Twin five questions

|No.|Question|Answer obtained from the normal UI|Result|
|---:|---|---|---|
|1|Critical track and WorkItem state at the selected Step?|At Step 12: Architecture/EIS option is in progress, HW/RTL carry-over review is blocked, SW feature flag is in progress, and Verification measurement is ready.|PASS|
|2|Causing DevelopmentEvent and propagation?|No causing DevelopmentEvent is recorded, and the UI says so instead of inventing one. Observable blocker propagation still shows EIS option → HW carry-over review → RTL Freeze/decision deadline.|PASS|
|3|Next commitment window and lost advantage?|The EIS Architecture option window closes at Step 13. Afterward HW interface changes require additional review/schedule adjustment; switching cost is 1 Step.|PASS|
|4|Expected transitions and unknown impacts per alternative?|Limited progress expects UHD60 EIS `PLANNED → IN_PROGRESS`, preserving immediate rollback while thermal remains unknown. Deferral expects EIS option `IN_PROGRESS → BLOCKED`, preserving measurement-based judgment while actual milestone delay remains unknown.|PASS|
|5|Actual Action/WorkItem/milestone/evidence changes after advance?|The observed Action changed and was later cancelled by the protection path. No WorkItem, milestone, or evidence change was observed, so the UI does not claim one.|PASS|

The second answer is intentionally a modeled unknown. Passing means the system exposes the missing event and
still shows only the propagation supported by observable state; it does not mean an event was inferred.

## 4. Interaction record

|Measure|Observed result|
|---|---|
|Wrong primary-action clicks|0|
|Role-original detail opens during questions 1–6|0|
|Raw JSON/ontology graph opens|0|
|Expected/observed/hidden misclassification|0|
|Automated complete-flow elapsed time|7.2 s in the recorded passing run|
|Applicable question failures|0/13|

The elapsed value is automation runtime, not a human task-time measurement. It must not be compared with the
10/30/60/90-second human targets or used as evidence of decision-speed improvement.

## 5. Responsive and accessibility evidence

|Gate|Result|Evidence|
|---|---|---|
|390px|PASS|No page overflow; mobile alternative cards and historical Step boundary work|
|768px|PASS|No page overflow; two-column decision context remains readable|
|Desktop|PASS|Complete Replay lifecycle and semantic comparison table|
|200% zoom equivalent|PASS|1280 physical-width assumption represented by a 640 CSS-pixel reflow viewport; no page overflow or information loss|
|Keyboard|PASS|First Tab exposes the skip link; Enter focuses `main#main-content`; visible focus ring on actions|
|Screen-reader semantics|PASS|One main landmark, named navigation, labeled regions, heading hierarchy, table caption/headers, live status and alerts|
|Automated accessibility|PASS|axe reports zero violations on 390, 640, 768, and desktop flows|
|Reduced motion|PASS|CSS disables animation/smooth scroll; programmatic section navigation uses `auto` when requested|
|Touch targets|PASS|Primary/secondary buttons, back link, selects, and disclosure summaries are at least 44px high|

The 640 CSS-pixel check is the deterministic reflow equivalent of 200% browser zoom on a 1280-pixel
reference viewport. A future human pilot should additionally repeat the task using the target corporate
browser's native zoom control.

## 6. Recovery and boundary evidence

|Scenario|Result|
|---|---|
|Partial review|Completed roles remain visible, failed role has a Korean reason, retry is available, and Chair action is absent|
|Aggregate conflict/stale state|Alert announces stale state, primary action is disabled, and refresh restores the current workspace|
|Historical Step|Commands, future dossier, decision, outcome, and current-only assumptions remain absent|
|Expected transition|Cards remain labeled as expected model output, separate from observed changes|
|Hidden outcome|Outcome remains unavailable until explicit Simulation Step advance|

## 7. Interpretation boundary

This report closes the fixture-only UX-F engineering gate. It does not prove human comprehension, human
task time, real decision-speed improvement, advice quality on company cases, Jira/Confluence integration,
or business value. Those require a later human baseline and read-only company pilot under C0 approval.
