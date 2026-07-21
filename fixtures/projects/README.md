# OPS-B Project fixture adaptation receipt

이 디렉터리는 `development-project.v1` authoring/validation 입력이다. OPS-C 전까지 runtime
Project API, DB aggregate 또는 UI data source가 아니다.

## Coverage

|Project|Lifecycle|주요 evidence posture|서로 다른 운영 질문|
|---|---|---|---|
|PROJECT-U|MASS_PRODUCTION|field measurement와 late/received 장시간 결과|관측 Issue를 완화하면서 KPI 손실과 차기 silicon 반복 Risk를 어떻게 다룰 것인가|
|PROJECT-V|PRE_SILICON_CLOSURE|오차 범위가 큰 model, late sign-off, future silicon 측정|불완전한 evidence에서 비가역 commitment와 공유 자원 충돌을 어떻게 제한할 것인가|
|PROJECT-W|SPEC_DEFINITION|초기 model, 이전 세대 lesson, late 고객 요구|data 부족에서 최소 spec만 고정하고 재작업 blast radius를 어떻게 줄일 것인가|

세 Project는 `open`, `treating`, `accepted`, `realized`, `closed` Risk와 `requested`, `late`,
`received` Evidence를 함께 포함한다. 숫자 risk score, source-authored `RiskLevel`과
`ProjectAttention`은 포함하지 않는다.

## `world.yaml` 사용 범위

참고본의 top-level `events`에서 다음과 같은 **상황 패턴만** 선택해 local synthetic 문맥으로
다시 작성했다.

- field에서 확인된 전력/thermal 현상과 차기 silicon lesson
- pre-silicon model uncertainty와 HW commitment window
- model 중심 area/performance spec trade-off
- evidence 요청 지연/도착, rework와 공유 측정 자원 충돌

원본의 project/role/risk/activity 구조, 점수, dice, 긴 role reasoning과 event ID/문장은 가져오지
않았다. 외부 파일은 runtime이나 test 입력이 아니며, manifest의 hash는 참고 revision을 추적하기
위한 receipt일 뿐이다.

## Historical boundary

Event에는 `effective_at_step`과 `observed_at_step`, Evidence에는 request/expected/available Step을
분리했다. `reconstruct_project_fixture_at_step`은 선택 Step 뒤의 Event를 역적용하고, 아직
관측되지 않은 Issue/Risk/Decision과 아직 도착하지 않은 evidence source를 반환하지 않는다.
