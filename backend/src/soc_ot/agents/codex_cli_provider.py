import json
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from soc_ot.agents.contracts import ProviderReviewResult, ProviderUsage, RoleReview
from soc_ot.agents.multi_role import (
    ChairProviderResult,
    ChallengerProviderResult,
    ChallengerReview,
    DecisionDossier,
    SimulatedDecision,
)
from soc_ot.agents.prompts import (
    CHAIR_INSTRUCTIONS,
    CHALLENGER_INSTRUCTIONS,
    ROLE_REVIEW_INSTRUCTIONS,
)
from soc_ot.agents.providers import ProviderUsageLimitError, StructuredReviewError
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import GUARDRAIL_METRIC_UNITS, DecisionType

ModelT = TypeVar("ModelT", bound=BaseModel)
ReasoningEffort = Literal["low", "medium", "high", "xhigh", "max"]

_FORBIDDEN_ITEM_TYPES = {
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "tool_call",
    "web_search",
}
_SAFE_ENVIRONMENT_KEYS = {
    "APPDATA",
    "CODEX_HOME",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


class CodexCliProvider:
    """ChatGPT-authenticated Codex CLI provider for the separate I7-C quality gate."""

    name = "codex-cli"

    def __init__(
        self,
        *,
        model: str = "gpt-5.6-luna",
        reasoning_effort: ReasoningEffort = "high",
        timeout_seconds: float = 180.0,
        executable: str | None = None,
    ) -> None:
        self.model = model
        self.challenger_model = model
        self.chair_model = model
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.command_prefix = _find_codex_command(executable)

    def preflight(self) -> None:
        completed = subprocess.run(
            [*self.command_prefix, "login", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
            env=_sanitized_environment(),
        )
        status = completed.stdout + completed.stderr
        if completed.returncode != 0 or "Logged in using ChatGPT" not in status:
            raise ValueError("CODEX_CLI_CHATGPT_LOGIN_REQUIRED")

    def review(self, packet: ObservableCasePacket, role_id: str) -> ProviderReviewResult:
        return self._review(packet, role_id, None)

    def review_with_feedback(
        self, packet: ObservableCasePacket, role_id: str, feedback: str
    ) -> ProviderReviewResult:
        return self._review(packet, role_id, feedback)

    def _review(
        self, packet: ObservableCasePacket, role_id: str, feedback: str | None
    ) -> ProviderReviewResult:
        instructions = (
            f"{ROLE_REVIEW_INSTRUCTIONS}\nAssigned role_id: {role_id}."
            " Use only IDs listed in valid_claim_ids and valid_option_ids. If "
            "valid_claim_ids is empty, every rationale_claim_ids and risk.claim_ids "
            "array must be empty, recommendation must be one of "
            "valid_recommendation_types, and recommended_option_id must be null. "
            "Keep the entire response, including reasoning, within 1500 output tokens."
            + _feedback_instruction(feedback)
        )
        parsed, request_id, usage = self._invoke(
            RoleReview,
            instructions,
            {
                "role_id": role_id,
                "valid_claim_ids": [item.claim_id for item in packet.claims],
                "valid_option_ids": [
                    item.option_id for item in packet.alternatives
                ],
                "valid_recommendation_types": _valid_role_recommendations(packet),
                "observable_case_packet": packet.model_dump(mode="json"),
            },
            "CODEX_CLI_ROLE",
        )
        return ProviderReviewResult(
            review=parsed,
            provider_request_id=request_id,
            returned_model=self.model,
            usage=usage,
        )

    def challenge(
        self, packet: ObservableCasePacket, reviews: list[RoleReview]
    ) -> ChallengerProviderResult:
        return self._challenge(packet, reviews, None)

    def challenge_with_feedback(
        self,
        packet: ObservableCasePacket,
        reviews: list[RoleReview],
        feedback: str,
    ) -> ChallengerProviderResult:
        return self._challenge(packet, reviews, feedback)

    def _challenge(
        self,
        packet: ObservableCasePacket,
        reviews: list[RoleReview],
        feedback: str | None,
    ) -> ChallengerProviderResult:
        parsed, request_id, usage = self._invoke(
            ChallengerReview,
            CHALLENGER_INSTRUCTIONS
            + " Keep the entire response, including reasoning, within 2000 output tokens."
            + _feedback_instruction(feedback),
            {
                "valid_claim_ids": [item.claim_id for item in packet.claims],
                "observable_case_packet": packet.model_dump(mode="json"),
                "independent_role_reviews": [
                    item.model_dump(mode="json") for item in reviews
                ],
            },
            "CODEX_CLI_CHALLENGER",
        )
        return ChallengerProviderResult(
            challenger=parsed,
            provider_request_id=request_id,
            returned_model=self.model,
            usage=usage,
        )

    def decide(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
    ) -> ChairProviderResult:
        return self._decide(packet, dossier, allowed_decision_types, None)

    def decide_with_feedback(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
        feedback: str,
    ) -> ChairProviderResult:
        return self._decide(packet, dossier, allowed_decision_types, feedback)

    def _decide(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
        feedback: str | None,
    ) -> ChairProviderResult:
        parsed, request_id, usage = self._invoke(
            SimulatedDecision,
            CHAIR_INSTRUCTIONS
            + " Copy every required_dissent_role_ids entry into "
            "dissent_acknowledged exactly. Use only supported_guardrail_metrics. "
            "When controlling a DDR or bandwidth risk, use metric_id DDR_BANDWIDTH "
            "and its registered unit GB/s. Every safeguard threshold must use mode "
            "exact with one numeric value, never range/qualitative/unknown. Keep the "
            "entire response, including reasoning, within 3000 output tokens."
            + _feedback_instruction(feedback),
            {
                "observable_case_packet": packet.model_dump(mode="json"),
                "decision_dossier": dossier.model_dump(mode="json"),
                "required_dissent_role_ids": [
                    item.role_id for item in dossier.dissent
                ],
                "supported_guardrail_metrics": GUARDRAIL_METRIC_UNITS,
                "allowed_decision_types": [
                    item.value for item in allowed_decision_types
                ],
            },
            "CODEX_CLI_CHAIR",
        )
        return ChairProviderResult(
            decision=parsed,
            provider_request_id=request_id,
            returned_model=self.model,
            usage=usage,
        )

    def _invoke(
        self,
        output_type: type[ModelT],
        instructions: str,
        input_payload: dict[str, object],
        error_prefix: str,
    ) -> tuple[ModelT, str | None, ProviderUsage]:
        with tempfile.TemporaryDirectory(prefix="soc-ot-codex-cli-") as temp_name:
            temp = Path(temp_name)
            schema_path = temp / "output.schema.json"
            output_path = temp / "final.json"
            schema_path.write_text(
                json.dumps(
                    strict_output_schema(output_type.model_json_schema()),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prompt = _isolated_prompt(instructions, input_payload)
            command = self._command(temp, schema_path, output_path)
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_seconds,
                    check=False,
                    env=_sanitized_environment(),
                )
            except subprocess.TimeoutExpired as error:
                raise ConnectionError(f"{error_prefix}_TIMEOUT") from error
            events = _parse_events(completed.stdout, error_prefix)
            request_id, usage = _validate_events(events, error_prefix)
            if completed.returncode != 0:
                detail = _event_error(events) or completed.stderr[-500:]
                if "usage limit" in detail.lower():
                    raise ProviderUsageLimitError("CODEX_CLI_USAGE_LIMIT")
                if _is_retryable_cli_error(detail):
                    raise ConnectionError(f"{error_prefix}_RETRYABLE")
                raise StructuredReviewError(f"{error_prefix}_FAILED")
            if not output_path.exists():
                raise StructuredReviewError(f"{error_prefix}_OUTPUT_MISSING")
            try:
                parsed = output_type.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
            except (ValidationError, ValueError) as error:
                raise StructuredReviewError(f"{error_prefix}_OUTPUT_INVALID") from error
            return parsed, request_id, usage

    def _command(self, temp: Path, schema_path: Path, output_path: Path) -> list[str]:
        return [
            *self.command_prefix,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--disable",
            "apps",
            "--disable",
            "browser_use",
            "--disable",
            "multi_agent",
            "--disable",
            "memories",
            "--disable",
            "goals",
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
            "-c",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "-m",
            self.model,
            "-C",
            str(temp),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
            "-",
        ]


def strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert Pydantic JSON Schema to the all-properties-required strict subset."""

    strict = deepcopy(schema)

    def visit(node: object) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(strict)
    return strict


def _find_codex_command(configured: str | None) -> list[str]:
    configured = configured or os.getenv("SOC_OT_CODEX_EXECUTABLE")
    if configured:
        return [configured]
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        node = shutil.which("node.exe") or shutil.which("node")
        if appdata and node:
            entrypoint = (
                Path(appdata)
                / "npm"
                / "node_modules"
                / "@openai"
                / "codex"
                / "bin"
                / "codex.js"
            )
            if entrypoint.exists():
                return [node, str(entrypoint)]
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("CODEX_CLI_NOT_INSTALLED")
    return [executable]


def _isolated_prompt(instructions: str, input_payload: dict[str, object]) -> str:
    return (
        "You are running inside the isolated I7-C evaluation harness. "
        "Do not use shell, files, network, web search, apps, MCP, tools, prior memory, "
        "or repository context. Use only the supplied JSON input. Return only the "
        "schema-conforming final object.\n\n"
        f"Task instructions:\n{instructions}\n\n"
        "Evaluation input JSON:\n"
        + json.dumps(input_payload, ensure_ascii=False, separators=(",", ":"))
    )


def _valid_role_recommendations(packet: ObservableCasePacket) -> list[str]:
    option_and_claim_required = {
        DecisionType.APPROVE,
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    }
    return [
        item.value
        for item in packet.allowed_decision_types
        if packet.claims or item not in option_and_claim_required
    ]


def _feedback_instruction(feedback: str | None) -> str:
    return f"\nValidator feedback for this clean retry: {feedback}" if feedback else ""


def _parse_events(stdout: str, error_prefix: str) -> list[dict[str, Any]]:
    events = []
    try:
        for line in stdout.splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("event is not an object")
                events.append(value)
    except (json.JSONDecodeError, ValueError) as error:
        raise StructuredReviewError(f"{error_prefix}_EVENT_STREAM_INVALID") from error
    return events


def _validate_events(
    events: list[dict[str, Any]], error_prefix: str
) -> tuple[str | None, ProviderUsage]:
    request_id = None
    usage: dict[str, object] | None = None
    for event in events:
        event_type = str(event.get("type", ""))
        if event_type == "thread.started":
            request_id = str(event.get("thread_id") or "") or None
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in _FORBIDDEN_ITEM_TYPES:
            raise StructuredReviewError(f"{error_prefix}_TOOL_USE_FORBIDDEN")
        if any(term in event_type for term in ("tool", "command", "mcp", "web")):
            raise StructuredReviewError(f"{error_prefix}_TOOL_USE_FORBIDDEN")
        if event_type == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    if usage is None:
        if _event_error(events):
            return request_id, ProviderUsage()
        raise StructuredReviewError(f"{error_prefix}_USAGE_MISSING")
    return request_id, ProviderUsage(
        input_tokens=_usage_int(usage.get("input_tokens")),
        output_tokens=_usage_int(usage.get("output_tokens")),
        estimated_cost_usd=0.0,
    )


def _event_error(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("type") == "error":
            return str(event.get("message", ""))
        if event.get("type") == "turn.failed":
            return str(event.get("error", ""))
    return ""


def _is_retryable_cli_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        item in lowered
        for item in ("rate limit", "temporarily unavailable", "timeout", "connection")
    )


def _usage_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _sanitized_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _SAFE_ENVIRONMENT_KEYS
    }
