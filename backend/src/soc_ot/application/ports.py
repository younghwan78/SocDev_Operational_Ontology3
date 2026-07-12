from typing import Protocol

from soc_ot.application.evaluation import CaseEvaluation
from soc_ot.domain.models import HiddenCase


class HiddenCaseReader(Protocol):
    def get(self, case_id: str) -> HiddenCase | None: ...


class EvaluationRepository(Protocol):
    def required_step(self, case_id: str) -> int: ...
    def evaluate(
        self,
        case_id: str,
        *,
        idempotency_key: str,
        aggregate_version: int,
        actor_id: str,
    ) -> CaseEvaluation: ...
    def latest(self, case_id: str) -> CaseEvaluation | None: ...
