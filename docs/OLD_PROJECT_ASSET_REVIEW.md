# 기존 프로젝트 자산 검토

> 검토 대상: `E:\56_Codex_SoC_Operational_Ontology`  
> 검토 방식: read-only 구조·문서·contract·핵심 코드 조사  
> 검토일: 2026-07-10  
> 새 목표 기준: `E:\59_Codex_SoC_Operational_Ontology\PROJECT_PLAN.md`

## 1. 검토 목적과 원칙

이 문서는 기존 프로젝트를 새 프로젝트의 출발점으로 삼기 위한 문서가 아니다. 새 목표에 편향을 주지 않으면서 재사용할 수 있는 기반 자산이 있는지 판단하기 위한 inventory이다.

검토 순서는 의도적으로 다음과 같이 진행했다.

1. `E:\59...`의 내부 논의만 바탕으로 새 목표와 전체 계획을 먼저 작성했다.
2. 새 계획의 첫 workflow, 성공 기준, 비목표를 고정했다.
3. 그 다음 `E:\56...`을 read-only로 조사했다.
4. 기존 기능과 새 목표가 비슷하다는 이유만으로 자동 재사용하지 않았다.

따라서 이 문서의 판단 기준은 “기존에 많이 구현했는가?”가 아니라 다음 세 가지이다.

- 새 첫 workflow에 직접 필요한가?
- 기존 domain assumption을 숨겨서 가져오지 않는가?
- 새 contract와 acceptance test를 더 단순하게 만족시키는가?

## 2. 기존 프로젝트의 현재 상태

### 2.1 규모

조사 시점의 대략적인 파일 규모는 다음과 같다.

|구분|수량|
|---|---:|
|Python source file|169|
|Frontend TS/TSX file|56|
|Python/Frontend test file|96|
|JSON Schema|31|
|Synthetic YAML file|30|

기존 문서의 Stage 45 완료 기록에는 backend `411 passed, 5 skipped`, frontend `55 passed`가 남아 있다. 이는 기존 문서의 기록이며 이번 검토에서 다시 실행해 확인한 값은 아니다.

### 2.2 저장소 상태 주의사항

조사 시점에 저장소는 detached HEAD 상태였고 다음 user-owned 변경이 있었다.

```text
D CURRENT_TASK.md
M docs/implementation/45_operational_ontology_core_integration_plan.md
M docs/implementation/45_operational_ontology_core_integration_result.md
M docs/validation/stage45_dry_run_2026-07-05.md
M docs/validation/stage45_value_validation_runbook.md
```

이 변경에는 손대지 않았다. 기존 저장소에서 향후 자산을 복사할 때도 commit 또는 명시한 파일 version을 기준으로 해야 하며, 현재 worktree를 정리하거나 변경해서는 안 된다.

### 2.3 기존 프로젝트가 실제로 만든 것

기존 프로젝트의 출발점은 `virtual role agent가 synthetic SoC universe에서 개발 의사결정을 simulation`하는 것이었다. 이후 45개 stage를 거치며 다음이 추가되었다.

- Project U/V/W synthetic development universe
- Scenario, Variant, IP, KPI, Issue, Evidence, Relation model
- YAML loader와 in-memory repository
- deterministic role-agent simulation
- scenario profile, what-if, evidence gap, confidence, review pack
- weekly activity, timeline, decision audit, de-risk backlog
- portfolio review board와 war-room 성격의 frontend
- FastAPI read surface
- optional PostgreSQL/pgvector adapter
- Stage 45의 단일 `OperationalDecisionCase`

Stage 45는 `Project U / UHD60 EIS power-gap review` 한 건을 대상으로 다음을 연결한다.

```text
request
  → exact project/scenario/event identity
  → affected objects
  → evidence and missing evidence
  → candidate options
  → seven role reviews
  → human review readiness
  → non-executable next actions
```

결과는 deterministic, read-only, fixture-derived이며 matched bandwidth evidence가 없어 `evidence_blocked` 상태가 된다.

## 3. 새 목표와 맞는 부분

### 3.1 Evidence-grounded contract

`OperationalStatement`는 description, supporting basis, derivation, confidence를 요구하고 generic statement를 일부 거부한다. `OperationalDecisionCase`도 evidence assessment, affected scope, readiness, next action, traceability, safety를 명시적으로 나눈다.

이는 새 계획의 `Fact → Claim → Advice → Decision` 분리와 Advice Contract의 좋은 참고 자료이다.

### 3.2 Exact context identity

`OperationalCaseResolver`는 `project_id`, `request_id`, `scenario_id`, `event_id`의 불일치를 거부하고 decision event가 정확히 하나일 때만 case를 구성한다.

이 원칙은 새 프로젝트에서도 유지 가치가 높다. 동일 Scenario 이름만 보고 서로 다른 Project/Variant/Evidence를 섞는 오류를 막아주기 때문이다.

### 3.3 Strict schema와 deterministic fixture

- Pydantic `extra="forbid"`
- model/JSON schema sync test
- 동일 입력의 run signature
- dangling relation validation
- fixture loader와 repository test

이 방식은 fixture-only 개발에서 regression을 막는 데 유용하다.

### 3.4 Evidence 부족을 결과로 노출

기존 Stage 45는 부족한 bandwidth evidence를 숨기지 않고 decision을 `evidence_blocked`로 유지한다. final decision, causal proof, score, owner assignment, ticket creation이 아니라는 safety flag도 명시한다.

이는 새 제품에서 abstain과 missing evidence를 핵심 동작으로 삼는 방향과 잘 맞는다.

### 3.5 인프라 경계

- read-only repository protocol
- fixture loader
- alias resolver
- relation resolver
- optional persistence adapter

이 component들은 domain model과 분리되어 있어 선택적으로 참고할 수 있다.

## 4. 새 목표와 어긋난 부분

### 4.1 Simulation과 role-agent가 제품의 중심

기존 구조의 중심은 `Development Event → Context Builder → 7 Role Agents → Risk/Validator → Board`이다. 이는 여러 조직 역할을 흉내 내는 데 초점이 있고, 실제 사람이 수행하는 하나의 decision workflow와 그 결과를 학습하는 데에는 초점이 약하다.

새 프로젝트는 role agent를 핵심 객체로 삼지 않는다. 사람의 실제 Role, Decision, Action, Outcome이 핵심이며 LLM은 그 흐름을 보조한다.

### 4.2 범위가 vertical slice보다 portfolio 방향으로 확장

기존 프로젝트는 Stage 44 기준으로 3개 Project, 23개 Scenario, 25개 request, 59개 development event, 60개 role activity, W1-W52 snapshot, 78개 portfolio item을 포함한다.

이 정도의 synthetic breadth는 시스템 데모에는 유리하지만 첫 decision의 정확성, 속도, 누락 감소를 깊게 평가하는 데에는 불필요한 운영 부담이다.

새 프로젝트는 12~20개의 작은 Change Review 정답 case를 먼저 만들고 breadth는 실제 가치 검증 후 늘린다.

### 4.3 실제 decision lifecycle이 없음

기존 `OperationalDecisionCase`는 다음처럼 안전하게 제한되어 있다.

```text
read_only = true
fixture_derived = true
not_final_decision = true
not_owner_assignment = true
not_ticket_creation = true
next action = non_executable
```

이는 기술 PoC로서는 적절하지만 새 목표의 핵심인 다음 폐루프를 구현하지 않는다.

```text
Advice
  → human accept/modify/reject
  → Decision
  → Action
  → Verification
  → Outcome
  → advice evaluation
```

### 4.4 시간·버전 모델이 충분하지 않음

기존 case는 exact identity와 source reference를 잘 보존하지만, 새 계획에서 요구하는 `valid_time`, `observed_time`, supersedes, 과거 시점 재구성이 핵심 aggregate에 충분히 드러나지 않는다.

최신 fixture를 deterministic하게 재실행하는 것과 과거 결정 당시의 지식 상태를 재현하는 것은 다른 요구사항이다.

### 4.5 Business value 검증이 기술 dry run에 머묾

기존 문서도 이 한계를 정확히 인정한다.

- human baseline 없음
- TAT 개선 측정 없음
- domain-owner accuracy 검증 없음
- real outcome 검증 없음

새 계획에서는 baseline과 telemetry를 Phase 0 contract에 포함하고, 로컬 fixture 검증을 business value로 표현하지 않는다.

### 4.6 구현된 기능 수가 핵심 가설보다 많음

weekly report, portfolio board, timeline, risk/what-if, pgvector, war-room UI는 각각 유용할 수 있지만 새 첫 workflow를 증명하기 전에는 제품 방향을 흐릴 수 있다.

기존 기능을 복사하면 “이미 있으니 살린다”는 sunk-cost 편향이 생길 가능성이 높다.

## 5. 자산 분류

### 5.1 새 contract 작성 후 재검토할 후보

다음은 바로 복사하지 않고, 새 contract와 acceptance test를 먼저 만든 후 구현 아이디어를 비교할 후보이다.

|기존 자산|후보 가치|재사용 전 조건|
|---|---|---|
|`backend/loaders/yaml_loader.py`|safe YAML, collection validation, 오류 보고|새 fixture manifest/schema와 맞는지 확인|
|`backend/models/common.py`|strict Pydantic base model|새 metadata/time/provenance 필드와 충돌 없는지 확인|
|`backend/ontology/alias_resolver.py`|alias collision과 canonical resolution|IP 전용 가정을 generic Entity Alias로 재설계|
|`backend/ontology/relation_resolver.py`|incoming/outgoing/path/dangling validation|새 typed relation과 temporal link 요구 반영|
|`backend/loaders/repository_protocols.py`|read/write interface 분리|기존 30개 collection별 method를 가져오지 않고 generic port로 축소|
|`backend/models/operational_decision_case.py`|evidence/readiness/traceability field 아이디어|새 Advice/Decision/Action/Outcome contract를 먼저 정의|
|관련 contract tests|strictness와 determinism 검증 패턴|기존 fixture ID와 Stage 45 behavior는 제거|

### 5.2 문서 또는 test pattern만 참고

|자산|판단|
|---|---|
|`synthetic_data/`|새 fixture를 만드는 archetype 참고만 허용; U/V/W universe를 기본 dataset으로 복사하지 않음|
|`schemas/`|field naming과 strict schema pattern 참고; 31개 schema 일괄 이전 금지|
|`backend/db/postgres/`|나중의 persistence ADR 자료; Phase 1에서 복사하지 않음|
|`backend/api/`|read API routing pattern 참고; 새 API contract freeze 후 비교|
|`docs/validation/`|value-validation runbook의 실패 경계 표현 참고|
|`source_data/ip_specs/`|synthetic capability archetype 참고; 실제 사내 source로 간주하지 않음|

### 5.3 새 MVP에 가져오지 않을 자산

|자산|이유|
|---|---|
|`backend/agents/`, `prompts/role_agents/`|7개 role simulation이 새 제품의 핵심이 아님|
|`backend/simulation/`의 기존 role cycle|실제 human decision lifecycle 대신 mock role output 중심|
|`backend/retrieval/pgvector_retriever.py` 및 vector fixture|첫 workflow에 필요성이 아직 증명되지 않음|
|`frontend/` 전체|war-room, portfolio, weekly, timeline 중심 IA가 새 Change Review Workspace와 다름|
|weekly/portfolio/backlog/audit/report modules|첫 vertical slice 밖의 파생 제품 기능|
|Stage 1~45 progression과 호환 layer|새 프로젝트에 legacy compatibility 의무를 만들 수 있음|
|기존 risk/what-if 결과|정량 simulator가 아니며 새 초기 제품에서 오해 가능성이 큼|

## 6. 편향 방지 재사용 절차

기존 코드의 재사용은 다음 순서를 지켜야 한다.

```text
새 목표/질문 고정
  → 새 contract 작성
  → 새 fixture와 expected result 작성
  → acceptance test 작성
  → 최소 구현 시도
  → 기존 자산과 비교
  → 더 단순하고 가정이 맞는 경우에만 port
```

재사용 module마다 ADR에 다음을 남긴다.

- 해결하려는 새 요구사항
- 처음부터 구현하는 비용
- 기존 module이 가진 domain assumption
- 그대로 사용, 축소 port, 개념만 참고 중 선택
- 가져오지 않은 부분과 이유
- 새 acceptance test 결과

기본값은 `재사용하지 않음`이다. 재사용은 명시적으로 입증해야 한다.

## 7. 최종 판단

기존 프로젝트는 실패한 프로젝트가 아니다. fixture, contract, deterministic validation, evidence grounding을 상당히 잘 구현했고 마지막 Stage 45에서 operational decision case 방향으로 수렴했다.

다만 새 목표는 다음 차이가 있다.

```text
기존:
synthetic universe와 여러 role의 판단을 재현하는 read-only simulation/review system

신규:
실제 한 의사결정의 상태, 근거, 조언, 사람의 선택, action, outcome을 연결하고
그 결과로 다음 조언을 평가하는 decision operations twin
```

따라서 기존 repository를 fork하거나 복사해서 시작하지 않는다. 새 저장소에서 fixture contract와 Decision Workflow를 clean baseline으로 구현한다. 이후 loader, alias/relation validation, strict contract test의 일부만 새 기준으로 선택적 port한다.

이 방식이면 기존 투자에서 학습은 얻되, 기존 stage와 UI, role-agent 구조가 새 제품 목표를 결정하는 상황을 피할 수 있다.
