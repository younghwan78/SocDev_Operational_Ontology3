from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.hidden_boundary import assert_hidden_free
from soc_ot.application.workspace_contracts import (
    PRIMARY_ACTION_BY_PHASE,
    PRIMARY_ACTION_LABELS_KO,
    DecisionWorkspaceProjectionV2,
    WorkspaceUxFixture,
)
from soc_ot.domain.models import WorkspacePhase

ROOT = Path(__file__).resolve().parents[2]
UX_FIXTURE = ROOT / "fixtures/ux/CASE-VR-001.workspace.v1.yaml"
LABELS = ROOT / "fixtures/dictionaries/labels.ko.yaml"


def _payload() -> dict[str, object]:
    loaded = yaml.safe_load(UX_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_case_vr_001_ux_fixture_validates_all_phases_and_workspace_v2() -> None:
    fixture = WorkspaceUxFixture.model_validate(_payload())

    assert fixture.case_id == "CASE-VR-001"
    assert {item.phase for item in fixture.phase_contents} == set(WorkspacePhase)
    assert fixture.workspace_example.projection_schema_version == "decision-workspace.v2"
    assert fixture.workspace_example.time_context.selected_step == 12
    assert fixture.workspace_example.workflow.primary_action == "RUN_VIRTUAL_REVIEW"
    expected_option_ids = {
        item.option_id for item in fixture.workspace_example.expected_option_transitions
    }
    assert expected_option_ids == {
        "OPT-SW-GUARDED",
        "OPT-DEFER-EIS",
    }


def test_phase_content_uses_canonical_primary_action_and_korean_label() -> None:
    fixture = WorkspaceUxFixture.model_validate(_payload())
    labels = yaml.safe_load(LABELS.read_text(encoding="utf-8"))
    assert isinstance(labels, dict)
    phase_labels = labels["WorkspacePhase"]
    action_labels = labels["WorkspaceAction"]
    assert isinstance(phase_labels, dict)
    assert isinstance(action_labels, dict)

    for item in fixture.phase_contents:
        expected_action = PRIMARY_ACTION_BY_PHASE[item.phase]
        assert item.primary_action == expected_action
        assert item.primary_action_ko == PRIMARY_ACTION_LABELS_KO[expected_action]
        assert phase_labels[item.phase.value]
        assert action_labels[expected_action] == item.primary_action_ko


def test_historical_workspace_disables_commands_and_matches_selected_step() -> None:
    payload = deepcopy(_payload()["workspace_example"])
    assert isinstance(payload, dict)
    time_context = payload["time_context"]
    development_twin = payload["development_twin"]
    assert isinstance(time_context, dict)
    assert isinstance(development_twin, dict)
    state = development_twin["state_at_selected_step"]
    assert isinstance(state, dict)
    time_context.update(
        {
            "selected_step": 10,
            "mode": "historical",
            "commands_allowed_at_selected_step": False,
        }
    )
    state["reconstructed_at_step"] = 10

    workspace = DecisionWorkspaceProjectionV2.model_validate(payload)

    assert workspace.time_context.mode == "historical"
    assert workspace.time_context.commands_allowed_at_selected_step is False


def test_historical_workspace_rejects_commands_and_future_causal_chain() -> None:
    payload = deepcopy(_payload()["workspace_example"])
    assert isinstance(payload, dict)
    time_context = payload["time_context"]
    development_twin = payload["development_twin"]
    assert isinstance(time_context, dict)
    assert isinstance(development_twin, dict)
    state = development_twin["state_at_selected_step"]
    causal_chains = development_twin["causal_chains"]
    assert isinstance(state, dict)
    assert isinstance(causal_chains, list)
    time_context.update(
        {
            "selected_step": 9,
            "mode": "historical",
            "commands_allowed_at_selected_step": True,
        }
    )
    state["reconstructed_at_step"] = 9

    with pytest.raises(ValidationError, match="HISTORICAL_WORKSPACE_COMMAND_FORBIDDEN"):
        DecisionWorkspaceProjectionV2.model_validate(payload)

    time_context["commands_allowed_at_selected_step"] = False
    with pytest.raises(ValidationError, match="FUTURE_CAUSAL_CHAIN_FORBIDDEN"):
        DecisionWorkspaceProjectionV2.model_validate(payload)


def test_expected_observed_and_pre_reveal_outcome_boundaries_fail_closed() -> None:
    workspace_payload = deepcopy(_payload()["workspace_example"])
    assert isinstance(workspace_payload, dict)
    expected = workspace_payload["expected_option_transitions"]
    assert isinstance(expected, list)
    first_expected = expected[0]
    assert isinstance(first_expected, dict)
    first_changes = first_expected["state_changes"]
    assert isinstance(first_changes, list)
    first_change = first_changes[0]
    assert isinstance(first_change, dict)
    first_change["provenance"] = "observed_event"

    with pytest.raises(ValidationError, match="EXPECTED_TRANSITION_PROVENANCE_MISMATCH"):
        DecisionWorkspaceProjectionV2.model_validate(workspace_payload)

    workspace_payload = deepcopy(_payload()["workspace_example"])
    assert isinstance(workspace_payload, dict)
    outcome = workspace_payload["outcome_and_evaluation"]
    assert isinstance(outcome, dict)
    outcome["expectation_vs_actual_ko"] = ["미공개 결과를 미리 표시"]

    with pytest.raises(ValidationError, match="PRE_REVEAL_OUTCOME_MUST_REMAIN_HIDDEN"):
        DecisionWorkspaceProjectionV2.model_validate(workspace_payload)


def test_workspace_fixture_and_contract_reject_hidden_fields() -> None:
    payload = _payload()
    assert_hidden_free(payload, error_code="HIDDEN_FIELD_IN_WORKSPACE_FIXTURE")
    tampered = deepcopy(payload)
    workspace = tampered["workspace_example"]
    assert isinstance(workspace, dict)
    workspace["outcome_paths"] = ["must-not-cross-boundary"]

    with pytest.raises(ValueError, match="HIDDEN_FIELD_IN_WORKSPACE_FIXTURE"):
        assert_hidden_free(tampered, error_code="HIDDEN_FIELD_IN_WORKSPACE_FIXTURE")


def test_workspace_contracts_are_registered_for_generation() -> None:
    assert CONTRACT_MODELS["decision-workspace.v2"] is DecisionWorkspaceProjectionV2
    assert CONTRACT_MODELS["workspace-ux-fixture.v1"] is WorkspaceUxFixture
