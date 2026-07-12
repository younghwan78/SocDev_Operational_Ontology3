from pathlib import Path

import pytest
from pydantic import ValidationError

from soc_ot.domain.models import Quantity, WorkItemStatus, validate_work_transition
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def test_case_vr_001_validates_with_hidden_contract() -> None:
    repository = FixtureRepository(ROOT / "fixtures")

    case = repository.validate_case("CASE-VR-001", include_hidden=True)

    assert case.current_step == 12
    assert len(case.tracks) == 4
    assert len(case.alternatives) == 2


def test_observable_serialization_contains_no_hidden_fields() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    payload = case.model_dump_json()

    assert "hidden_root_causes" not in payload
    assert "outcome_paths" not in payload


def test_invalid_unit_fails() -> None:
    with pytest.raises(ValidationError):
        Quantity.model_validate({"mode": "exact", "unit": "Gbps", "value": 10})


def test_invalid_quantity_shape_fails() -> None:
    with pytest.raises(ValidationError):
        Quantity.model_validate(
            {"mode": "range", "unit": "GB/s", "lower_bound": 20, "upper_bound": 10}
        )


def test_invalid_work_transition_fails() -> None:
    with pytest.raises(ValueError, match="invalid work transition"):
        validate_work_transition(WorkItemStatus.PLANNED, WorkItemStatus.VERIFIED)


def test_dangling_dependency_fails() -> None:
    repository = FixtureRepository(ROOT / "fixtures")
    payload = repository.load_observable("CASE-VR-001").model_dump(mode="json")
    payload["work_items"][0]["dependency_ids"] = ["WORK-MISSING"]

    with pytest.raises(ValidationError, match="dangling work dependency"):
        type(repository.load_observable("CASE-VR-001")).model_validate(payload)

