# ADR-0004: Adjacent topology ablation stop rule

> Status: ACCEPTED
> Date: 2026-07-14

## Context

기존 live ablation은 B3를 B1과 직접 비교했다. 이 방식은 독립 Role Agent가 만드는
B2의 가치와 Challenger·simulated Chair가 만드는 B3의 가치를 분리하지 못한다.
따라서 B3가 추가 가치를 만들지 않아도 B2의 기여 때문에 `keep_b3`가 선택될 수 있고,
반대로 B2만 유효한 경우에도 `release_b2`를 표현할 수 없었다.

`eval-2026-07-14.2`에는 fresh validation 2개와 sealed-unseen 2개가 있다. 이 release는
Step 4 정책을 적용하기 전에 동결되었으며, Step 4는 prompt, fixture hidden outcome,
expected result 또는 decision policy를 변경하지 않는다.

## Decision

동일 case의 인접 topology만 비교한다.

|비교|질문|최소 기여 case|
|---|---|---:|
|B1 over B0|단일 Architecture/System Agent가 유효한 concern·safeguard 또는 deterministic 개선을 추가하는가|1/4|
|B2 over B1|독립 Role Agent들이 단일 Agent에 없는 유효한 기여를 추가하는가|3/4|
|B3 over B2|Challenger·simulated Chair가 multi-role dossier에 없는 유효한 기여를 추가하는가|3/4|

후보 topology는 모든 fresh case에서 Process gate를 통과하고 baseline보다 어떤
deterministic Process 항목도 후퇴시키지 않아야 한다. 다음만 추가 가치로 계산한다.

- 고유 concern을 제출한 새 Role ID
- 새 canonical safeguard metric
- 검증된 Challenger objection
- false에서 true로 개선된 deterministic Process 항목

문장 표현 차이와 decision family 변경 자체는 추가 가치로 세지 않는다.

선택 순서는 다음과 같다.

1. B3 over B2 gate가 통과하면 `keep_b3`
2. 그렇지 않고 B2 over B1 gate가 통과하면 `release_b2`
3. 그렇지 않고 B1 over B0 gate가 통과하면 `release_b1`
4. 나머지는 `release_b0`

각 stop rule은 각각 B3, B2, B1, B0를 `selected_topology`로 기록한다. 선택된 topology가
모든 fresh Process gate를 통과하지 못하면 `release_gate_passed=false`이며 CLI는 실패로
종료한다. 즉 `release_b0`는 무조건적인 품질 합격을 뜻하지 않는다.

선택 결과는 stability 대상인 release candidate다. Validation과 sealed stability를
통과하기 전에는 durable dossier workflow의 runtime 기본 topology를 변경하지 않는다.

## Evidence discipline

Replay 또는 Replay 기반 test double은 비교 계약과 artifact 생성을 검증할 뿐 Role
Agent의 실제 가치를 증명하지 않는다. 최종 topology 근거는 frozen v2 packet을 사용한
live ablation에서만 얻는다. Sealed 결과를 보고 prompt·validator를 조정하지 않으며,
실패 원인을 분석하려면 현재 release를 robustness 근거에서 retire한다.

## Consequences

- B2를 독립적인 release 후보로 선택할 수 있다.
- B3의 비용과 복잡성은 Challenger·Chair 고유 기여가 있을 때만 유지된다.
- v2 fresh corpus가 4개이므로 기존 3/5 문구는 3/4로 교체된다.
- 이전 `eval-2026-07-11.1`의 예비 `keep_b3`는 현재 release 판정에 재사용하지 않는다.
- 선택된 candidate의 runtime 활성화는 해당 topology stability gate 이후에 수행한다.
