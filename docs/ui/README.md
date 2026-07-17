# UI documents

화면 구현과 사용성 관찰을 둔다. Persona, 승인 경계와 usability 질문은
`../readiness/02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md`가 소유한다.

- 상세 UX 방향: `../../internal_docs/26.07.16 결정 중심 UX 설계.md`
- 한국어 용어와 표현 기준: `KOREAN_UI_GLOSSARY.md`
- UX-A 실행 fixture: `../../fixtures/ux/CASE-VR-001.workspace.v1.yaml`
- UX-B 목록: Backend-ranked `decision-list-item.v1`을 사용하는 `/decisions`
- UX-C 상세: selected Step을 지원하는 `decision-workspace.v2` 기반 `/decisions/:caseId`
- UX-D 판단 비교: Backend-owned 선택지 비교, Dossier 일치·이견·확인 필요,
  fact/inference/assumption/unknown과 접힌 Role 원문
- UX-E 실행·결과: durable decision/outcome/evaluation을 연결한 Action Plan, Safeguard,
  Rollback, 관측 상태 변화, 예상 대비 실제, 과정/결과 평가와 학습
- 생성 계약: `../../contracts/generated/decision-workspace.v2.schema.json`,
  `../../contracts/generated/workspace-ux-fixture.v1.schema.json`,
  `../../contracts/generated/decision-list-item.v1.schema.json`
