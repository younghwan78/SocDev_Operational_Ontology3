# Enterprise read-only pilot handoff runbook

> Status: TEMPLATE — NOT AUTHORIZED FOR LIVE USE
>
> Package: `fixtures/enterprise/handoff/handoff-package.v1.yaml`
>
> Authority: ADR-0017

이 문서는 사외에서 검증한 코드와 사내에서만 확인할 수 있는 값을 연결하는 고정 절차다.
현재 저장소에는 실제 connector, 회사 데이터, 인증 구현, credential, import 명령, write-back
경로가 없다.

## 0. 반입 전 무결성 확인

```powershell
uv run soc-ot enterprise validate-handoff
uv run soc-ot contracts export --check
powershell -File scripts/check-secrets.ps1
```

성공 조건은 package hash와 네 계약이 일치하고 `live use authorized=false`,
`write-back implemented=false`가 출력되는 것이다. 실패하면 파일을 임의로 고쳐 통과시키지
말고 변경 이유와 ADR 필요 여부를 먼저 검토한다.

예상 console output:

```text
Validated handoff package=enterprise-internal-handoff.1, artifacts=4,
mapping_templates=2, internal_items=11, live use authorized=false;
write-back implemented=false.
```

## 1. C0 사내 discovery

사내 승인된 작업 사본에서 다음을 확인한다. 실제 값, export, URL, user/group, token은 이
저장소나 Git history에 넣지 않는다.

1. `environment-worksheet.v1.yaml`의 각 `INTERNAL_REQUIRED` 항목에 대한 소유자와 근거를
   사내 기록 시스템에 남긴다.
2. 두 mapping template에 실제 source field/status를 대응시킨다.
3. source stable identity, version, effective/observed/source-updated/ingested time 의미를
   샘플로 검증한다.
4. source ACL과 classification이 Frontend/API/model/Role packet/log 노출 정책으로
   fail-closed 되는지 확인한다.
5. pilot 대상은 승인된 Project 하나만 선정한다.

이 단계의 결과는 운영 가능한 adapter가 아니라 C1 승인에 필요한 schema-fit 및 위험
목록이다.

## 2. Validate

```powershell
uv run soc-ot enterprise validate-source
uv run soc-ot enterprise validate-handoff
```

중단 조건:

- stable identity, version 또는 네 시간 의미가 불명확함
- ACL/classification/retention/owner 중 하나가 미확인
- Project allowlist가 없거나 둘 이상임
- credential 또는 회사 export가 working tree에 존재함

## 3. Dry-run

승인된 비식별/합성 입력으로만 수행한다.

```powershell
uv run soc-ot enterprise dry-run --output output/enterprise-dry-run.json
```

반드시 `write_performed=false`, `canonical_import_authorized=false`여야 한다. quarantine,
중복 identity/Event, silent drop, unknown freshness가 있으면 다음 단계로 가지 않는다.

## 4. Review

```powershell
uv run soc-ot enterprise emulate-security --output output/enterprise-security.json
```

ACL exposure, credential leak, write attempt, silent drop, duplicate Event, reconciliation mismatch의
목표값은 모두 0이다. 합성 결과는 사내 평가 결과가 아니며 package에는 `NOT_EVALUATED`로
남는다.

## 5. Import — C1 승인 전 금지

이 저장소에는 import 명령이 없다. C1에서 다음을 모두 승인하기 전에는 구현하지 않는다.

- Project 1개 allowlist와 data/security/human decision owner
- read-only adapter 경계와 최소 ACL
- rollback trigger, 접근 철회 절차, metadata-only audit 보존
- sanitized sample의 contract/schema fit
- 모든 pass/stop 기준과 승인 기록

## 6. Reconcile — 승인된 import 후에만

source/candidate count, stable identity, external version, checkpoint, quarantine, Event 중복,
freshness를 독립적으로 대조한다. 하나라도 맞지 않으면 접근을 중지하고 canonical truth를
갱신하지 않은 채 mapping/discovery 단계로 되돌린다.

## Handoff 판정

`READY_FOR_INTERNAL_DISCOVERY`는 반입 가능한 template 상태일 뿐 live readiness가 아니다.
다음 중 하나라도 참이면 `STOP`이다.

- 실제 ACL을 확인하지 못했거나 restricted content가 노출됨
- credential/company export가 파일·로그·report에 남음
- write attempt가 1회 이상 발생함
- source freshness가 unknown인데 current로 표시됨
- silent drop, duplicate Event, reconciliation mismatch가 1개 이상임
- C1 사람 승인이 없는데 import/reconcile 실행 경로가 존재함
