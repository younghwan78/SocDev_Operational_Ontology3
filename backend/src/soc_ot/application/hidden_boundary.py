from collections.abc import Mapping, Sequence

HIDDEN_FIELD_DENYLIST = frozenset(
    {
        "hidden_root_causes",
        "outcome_paths",
        "expected_result",
        "acceptable_decision_types",
    }
)


def assert_hidden_free(
    value: object,
    *,
    error_code: str = "HIDDEN_FIELD_IN_OBSERVABLE_OUTPUT",
) -> None:
    if isinstance(value, Mapping):
        forbidden = HIDDEN_FIELD_DENYLIST & value.keys()
        if forbidden:
            raise ValueError(f"{error_code}:{sorted(forbidden)}")
        for nested in value.values():
            assert_hidden_free(nested, error_code=error_code)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for nested in value:
            assert_hidden_free(nested, error_code=error_code)
