# Agent runtime and security policy

> Status: APPROVED  
> Date: 2026-07-11

## 1. Purpose

This policy fixes the Agent execution boundary, provider behavior, resource limits, and protection of hidden fixtures. Agent output is advisory candidate data until schema and deterministic policy validation accept it.

## 2. Provider modes

|Mode|Purpose|Network/API key|Release role|
|---|---|---|---|
|`replay`|development, CI, deterministic regression|not required|canonical acceptance provider|
|`openai`|real model behavior and I7 stability|required|supplementary live-provider gate|

The first live adapter uses the OpenAI Responses API with Structured Outputs. Model identifiers are configuration and audit metadata, not domain constants.

Initial local defaults as of 2026-07-11:

```dotenv
SOC_OT_ROLE_MODEL=gpt-5.4-mini
SOC_OT_CHALLENGER_MODEL=gpt-5.5
SOC_OT_CHAIR_MODEL=gpt-5.5
```

For a formal baseline, pin a dated model snapshot when the provider offers one. A model alias may move, so every run stores the provider-returned model identifier.

## 3. Agent topology

- Role Router selects at most 5 Role Agents.
- Required roles are derived from affected development objects, not a fixed all-role panel.
- One Challenger examines the initial independent reviews.
- At most two selected roles may revise after the challenge; each selected role may revise at most once.
- One simulated Decision Chair chooses only from observable option IDs.
- Agents do not message one another freely; the orchestrator owns round order and inputs.

## 4. Hard execution limits

|Limit|Value|
|---|---:|
|Selected Role Agents|5 maximum|
|Review rounds|2 maximum: initial plus one revision|
|Concurrent provider calls|3 maximum|
|Revised roles per case|2 maximum|
|Logical Agent calls per case|9 maximum|
|Provider attempts including retry/repair|12 maximum|
|Role timeout|120 seconds|
|Challenger timeout|120 seconds|
|Chair timeout|180 seconds|
|Case wall-clock deadline|900 seconds|
|Role output budget|1,500 tokens|
|Challenger output budget|2,000 tokens|
|Chair output budget|3,000 tokens|
|Total output budget across all attempts|20,000 tokens|
|Transport retry|1|
|Schema-repair retry|1|

The nine logical calls are `5 initial roles + 1 Challenger + up to 2 revisions + 1 Chair`. Every transport retry and schema-repair attempt consumes the provider-attempt, token, cost, and time budgets.

Reserve Chair tokens, one provider attempt, and estimated cost before scheduling optional revisions. A request that would exceed any hard cap is rejected with `AGENT_BUDGET_EXCEEDED`.

## 5. Retry and failure policy

- Retry once for a transient transport/provider error.
- A syntactically invalid structured result gets one schema-repair attempt.
- A policy violation gets one clean retry with violation feedback, then the run fails.
- Timeout is terminal for that agent attempt; the orchestrator may continue only if the decision policy says the missing role is non-mandatory.
- The case deadline stops scheduling calls, requests cancellation for in-flight work, and marks unfinished mandatory steps failed.
- Provider unavailability yields a failed live run. It never silently switches to ReplayProvider.
- ReplayProvider must be selected explicitly for deterministic execution.

There is no unbounded autonomous loop.

## 6. Input isolation and prompt-injection defense

Fixture text is untrusted data even when locally authored.

- Place each source field in a typed, delimited data section.
- State that text inside evidence, issue descriptions, and comments cannot alter system policy.
- Do not interpolate raw fixture text into system instructions.
- Allow no runtime web search, shell, filesystem, database query, or arbitrary tool calls from a Role Agent, Challenger, or Chair.
- Agents receive a projected Observable Case Packet, never a repository handle.
- Validate output with strict Pydantic models and reject unknown fields.
- Reject citations to source IDs absent from the packet.

## 7. Hidden-fixture boundary

The main API must not provide a hidden-fixture endpoint, including a development-only route.

Hidden data is accessible only to:

- `OutcomeRepository`
- `EvaluationRepository`
- an authoring CLI guarded by `SOC_OT_AUTHORING_MODE=1`

PostgreSQL grants reinforce the application boundary. The API and Role/Chair steps use a runtime database role with no `SELECT` permission on the hidden schema. Outcome/Evaluation steps open a separate connection with the outcome role. Integration tests execute a direct hidden query with runtime credentials and require PostgreSQL to deny it.

Planned authoring command:

```powershell
$env:SOC_OT_AUTHORING_MODE = "1"
uv run python -m soc_ot.cli dev inspect-hidden --case-id CASE-VR-001
```

The CLI must refuse execution when authoring mode is off. It prints a visible `AUTHORING/HIDDEN` banner, writes an audit record, and must not be callable by the worker. Hidden content is absent from Agent prompts, run inputs, ordinary logs, API responses, browser state, and ReplayProvider observable snapshots.

## 8. Secrets

- Store provider keys only in environment variables or a future company secret manager.
- Keep `.env` and `.env.local` ignored; commit only `.env.example` with blank values.
- Never write keys to database rows, fixtures, exception messages, telemetry, or snapshots.
- Redact `Authorization`, cookies, tokens, connection passwords, and provider request headers.
- Fail startup in `openai` mode when the key is missing; do not prompt interactively.
- Run the repository secret scan in CI.

## 9. Logging and audit

Every Agent attempt records:

```text
run_id, attempt_id, case_id, role_id, round
provider, requested_model, returned_model
prompt_bundle_version, policy_version, contract_version
observable_packet_hash
started_at, completed_at, duration_ms
input_tokens, output_tokens, estimated_cost
retry_reason, validation_result, final_status
```

Logs use stable IDs and counts. Ordinary logs do not contain complete prompts, evidence bodies, or raw provider responses.

## 10. Retention

|Artifact|Default local retention|
|---|---|
|Accepted normalized reviews and decisions|project lifetime|
|Audit metadata and policy violations|project lifetime|
|Raw live-provider request/response, redacted|30 days|
|Transient SSE/poll progress events|7 days|
|API keys and secrets|never persisted|

Retention is configurable for the future company environment. Deletion must preserve immutable hashes and the fact that an artifact existed without retaining its sensitive body.

## 11. Cost and cancellation

- Track tokens and estimated cost per attempt and case.
- Enforce `SOC_OT_MAX_CASE_COST_USD` before starting each next call.
- A batch evaluation also enforces `SOC_OT_MAX_EVALUATION_COST_USD` before its first live call and before each next case.
- User cancellation stops scheduling new calls; in-flight calls may finish but their results are marked `discarded_after_cancel`.
- A partial Dossier cannot be approved when a mandatory role failed or was cancelled.
- The run plan reports reserved and remaining logical calls, provider attempts, tokens, cost, and timeout before execution.

## 12. Prompt and provider versioning

Prompts live under `backend/src/soc_ot/agents/prompts/<bundle-version>/`. Each bundle contains Role, Challenger, and Chair templates plus a manifest of hashes. Prompt changes require a new bundle version and evaluation report; they are never edited only in a database or UI.

Do not request, expose, or persist private chain-of-thought. Persist only the strict structured output, atomic claims, concise decision rationale, validation results, and provider metadata needed for audit.

## 13. Policy acceptance tests

- Role/Chair dependency graph cannot import hidden repositories
- runtime database credentials cannot read the hidden schema
- observable packet rejects hidden fields and unknown source IDs
- injection-like fixture text cannot change output schema or tool policy
- call, round, timeout, token, and cost caps are enforced
- no silent provider fallback
- missing key fails only live mode; replay remains runnable
- secrets and hidden values are absent from logs and snapshots
- authoring CLI refuses execution without explicit authoring mode

## 14. Official implementation references

- OpenAI model selection: <https://developers.openai.com/api/docs/models>
- GPT-5.4 API capabilities: <https://developers.openai.com/api/docs/models/gpt-5.4>
- OpenAI developer resources and Structured Outputs guide: <https://developers.openai.com/resources>
