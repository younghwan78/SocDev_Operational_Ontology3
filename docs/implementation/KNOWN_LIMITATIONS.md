# Known limitations

> Verified: 2026-07-23

- The local product uses synthetic fixtures. It does not connect to company Confluence or Jira.
- The Decision Chair is explicitly simulated and has no approval authority.
- ReplayProvider proves orchestration, policy, failure recovery, and evaluation reproducibility; it does not prove that multi-role LLMs add decision value.
- Frozen Codex CLI ablation and B2 stability passed locally, but this does not prove statistical generalization or actual company business value.
- The OpenAI Responses API cost/latency surface still requires a user-supplied API key, explicit current token-price settings, and cost acknowledgement; Codex CLI subscription usage cannot substitute for it.
- Outcome rules are a closed registry for the eight frozen cases, not a general semiconductor physics simulator.
- The 12-case corpus, including four fresh validation/sealed cases, is suitable for local pipeline and release verification, not statistical generalization.
- Local SSE follows persisted events with sequence resume, heartbeat, and a bounded 30-second connection; the UI uses polling as the reconnect fallback.
- Provider token cost is an estimate based on operator-supplied rates and must be refreshed when pricing changes.
- Company security, identity, retention, and write-back controls require a separate pilot design review.
- ENT-A now provides a source-neutral enterprise identity/time envelope, opaque ACL/classification
  metadata and deletion/restriction payload boundary. There is still no Jira/Confluence adapter,
  mapping registry, real ACL inheritance, incremental sync, tombstone reconciliation, retention or
  unstructured-extraction review path. Direct live company connection remains NO-GO.
- Codex CLI evaluation artifacts contain aggregate model usage and normalized results, while normal durable worker attempt telemetry remains Replay-verified unless the Responses API worker is separately authorized.
- UX-H Decision-centered v1 material remains reproducible, and OPS-F now adds a Project-centered v2
  protocol with three hash-pinned Projects, six baseline surfaces and eleven frozen tasks. Both study
  conditions still contain zero completed independent observations. Reviewer comprehension, task-time
  improvement and business value remain unproven. The owner deferred human observation on 2026-07-23,
  and UX-I completed only as engineering-proxy work; UX-J/K remain limited to the same evidence class.
  This exception does not pass the human Gate
  or support any human usability, decision-speed, advice-quality or business-value claim.
