# Known limitations

> Verified: 2026-07-11

- The local product uses synthetic fixtures. It does not connect to company Confluence or Jira.
- The Decision Chair is explicitly simulated and has no approval authority.
- ReplayProvider proves orchestration, policy, failure recovery, and evaluation reproducibility; it does not prove that multi-role LLMs add decision value.
- Live OpenAI stability and B0-B3 marginal-value gates require a user-supplied API key, explicit current token-price settings, and cost acknowledgement. They were not executed when no key was present.
- Outcome rules are a closed registry for the eight frozen cases, not a general semiconductor physics simulator.
- The eight-case corpus shares a base structure and is suitable for pipeline verification, not statistical generalization.
- Local SSE follows persisted events with sequence resume, heartbeat, and a bounded 30-second connection; the UI uses polling as the reconnect fallback.
- Provider token cost is an estimate based on operator-supplied rates and must be refreshed when pricing changes.
- Company security, identity, retention, and write-back controls require a separate pilot design review.
- Live provider attempt-level observations have not been produced because no live run was authorized; Replay metadata proves the audit schema and deterministic flow, not real-provider latency or grounding quality.
