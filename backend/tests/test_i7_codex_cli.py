import json
import subprocess
from pathlib import Path

import pytest

from soc_ot.agents.codex_cli_provider import (
    CodexCliProvider,
    _valid_role_recommendations,
    strict_output_schema,
)
from soc_ot.agents.contracts import RoleReview
from soc_ot.agents.providers import ProviderUsageLimitError, StructuredReviewError
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _packet(case_id: str = "CASE-VR-001"):
    case = FixtureRepository(ROOT / "fixtures").load_observable(case_id)
    return build_observable_case_packet(case)


def test_strict_schema_requires_every_root_and_nested_property() -> None:
    schema = strict_output_schema(RoleReview.model_json_schema())

    assert set(schema["required"]) == set(schema["properties"])
    risk = schema["$defs"]["RiskAssessment"]
    assert set(risk["required"]) == set(risk["properties"])
    assert "default" not in schema["properties"]["schema_version"]


def test_no_claim_case_limits_role_to_risk_limiting_recommendations() -> None:
    packet = _packet("CASE-VR-005")

    assert packet.claims == []
    assert _valid_role_recommendations(packet) == [
        "DEFER_UNTIL_TRIGGER",
        "ESCALATE",
    ]


def test_codex_cli_provider_is_isolated_structured_and_metered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-forwarded")
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["environment"] = kwargs["env"]
        observed["input"] = kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "schema_version": "role-review.v1",
                    "role_id": "architecture_system",
                    "recommendation": "COLLECT_MINIMUM_EVIDENCE",
                    "recommended_option_id": None,
                    "rationale": "현재 근거의 한계를 유지한다.",
                    "rationale_claim_ids": [],
                    "risks": [
                        {
                            "risk_id": "R-1",
                            "statement": "측정 전 불확실성",
                            "severity": "medium",
                            "claim_ids": [],
                            "mitigation": "최소 측정 후 재검토",
                        }
                    ],
                    "information_gaps": ["실측값"],
                    "unique_concern": "interface freeze 영향",
                    "no_unique_concern": False,
                    "confidence": "medium",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        events = [
            {"type": "thread.started", "thread_id": "cli-thread-1"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "structured"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        ]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join(json.dumps(item) for item in events),
            stderr="",
        )

    monkeypatch.setattr(
        "soc_ot.agents.codex_cli_provider.subprocess.run", fake_run
    )
    provider = CodexCliProvider(
        model="gpt-5.6-luna",
        reasoning_effort="high",
        executable="codex.exe",
    )

    result = provider.review(_packet(), "architecture_system")

    command = observed["command"]
    assert isinstance(command, list)
    assert "gpt-5.6-luna" in command
    assert 'model_reasoning_effort="high"' in command
    assert result.provider_request_id == "cli-thread-1"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert "OPENAI_API_KEY" not in environment
    prompt = observed["input"]
    assert isinstance(prompt, str)
    assert '"valid_claim_ids"' in prompt
    assert '"valid_option_ids"' in prompt


def test_codex_cli_provider_rejects_any_tool_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **_kwargs):
        events = [
            {"type": "thread.started", "thread_id": "cli-thread-2"},
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "dir"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        ]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join(json.dumps(item) for item in events),
            stderr="",
        )

    monkeypatch.setattr(
        "soc_ot.agents.codex_cli_provider.subprocess.run", fake_run
    )
    provider = CodexCliProvider(executable="codex.exe")

    with pytest.raises(StructuredReviewError, match="TOOL_USE_FORBIDDEN"):
        provider.review(_packet(), "architecture_system")


def test_codex_cli_provider_marks_usage_limit_as_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **_kwargs):
        events = [
            {"type": "thread.started", "thread_id": "cli-thread-3"},
            {"type": "error", "message": "You've hit your usage limit."},
            {
                "type": "turn.failed",
                "error": {"message": "You've hit your usage limit."},
            },
        ]
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="\n".join(json.dumps(item) for item in events),
            stderr="",
        )

    monkeypatch.setattr(
        "soc_ot.agents.codex_cli_provider.subprocess.run", fake_run
    )
    provider = CodexCliProvider(executable="codex.exe")

    with pytest.raises(ProviderUsageLimitError, match="CODEX_CLI_USAGE_LIMIT"):
        provider.review(_packet(), "architecture_system")
