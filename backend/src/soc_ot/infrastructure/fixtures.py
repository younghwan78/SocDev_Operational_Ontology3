from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from soc_ot.domain.models import ExpectedResult, HiddenCase, ObservableCase

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if isinstance(payload, dict) and "extends" in payload:
        base_name = str(payload.pop("extends"))
        base = _load_yaml(path.parent / f"{base_name}.yaml")
        if not isinstance(base, dict):
            raise ValueError("fixture base must be an object")
        return {**base, **payload}
    return payload


class FixtureRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _load(self, relative_path: str, model_type: type[ModelT]) -> ModelT:
        return model_type.model_validate(_load_yaml(self.root / relative_path))

    def load_observable(
        self, case_id: str, relative_path: str | None = None
    ) -> ObservableCase:
        if relative_path is None:
            evaluation_path = self.root / f"cases/observable/{case_id}.yaml"
            relative_path = (
                f"cases/observable/{case_id}.yaml"
                if evaluation_path.exists()
                else f"cases/development/{case_id}.yaml"
            )
        return self._load(relative_path, ObservableCase)

    def load_hidden(
        self, case_id: str, relative_path: str | None = None
    ) -> HiddenCase:
        return self._load(relative_path or f"cases/hidden/{case_id}.yaml", HiddenCase)

    def load_expected(
        self, case_id: str, relative_path: str | None = None
    ) -> ExpectedResult:
        return self._load(relative_path or f"expected/{case_id}.yaml", ExpectedResult)

    def validate_evaluation_case(
        self,
        case_id: str,
        *,
        observable_path: str | None = None,
        hidden_path: str | None = None,
        expected_path: str | None = None,
    ) -> tuple[ObservableCase, HiddenCase, ExpectedResult]:
        observable = self.load_observable(case_id, observable_path)
        hidden = self.load_hidden(case_id, hidden_path)
        expected = self.load_expected(case_id, expected_path)
        if {observable.case_id, hidden.case_id, expected.case_id} != {case_id}:
            raise ValueError("evaluation source case ids differ")
        if len({observable.fixture_version, hidden.fixture_version, expected.fixture_version}) != 1:
            raise ValueError("evaluation source fixture versions differ")
        option_ids = {item.option_id for item in observable.alternatives}
        path_ids = {item.option_id for item in hidden.outcome_paths}
        if option_ids != path_ids:
            raise ValueError("outcome paths must exactly match observable option ids")
        return observable, hidden, expected

    def validate_case(self, case_id: str, *, include_hidden: bool = False) -> ObservableCase:
        observable = self.load_observable(case_id)
        if case_id in self.development_case_ids():
            if include_hidden:
                raise ValueError("development case has no hidden outcome")
            return observable
        expected = self.load_expected(case_id)
        if expected.fixture_version != observable.fixture_version:
            raise ValueError("expected and observable fixture versions differ")
        if include_hidden:
            hidden = self.load_hidden(case_id)
            if hidden.fixture_version != observable.fixture_version:
                raise ValueError("hidden and observable fixture versions differ")
            option_ids = {item.option_id for item in observable.alternatives}
            path_ids = {item.option_id for item in hidden.outcome_paths}
            if option_ids != path_ids:
                raise ValueError("outcome paths must exactly match observable option ids")
        return observable

    def case_ids(self) -> list[str]:
        return sorted(path.stem for path in (self.root / "cases/observable").glob("*.yaml"))

    def development_case_ids(self) -> list[str]:
        return sorted(path.stem for path in (self.root / "cases/development").glob("*.yaml"))
