from fastapi.testclient import TestClient

from soc_ot.api.main import create_app
from soc_ot.cli.main import main


def test_health_is_available_without_database_or_api_key() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_cli_reports_scaffold(capsys: object) -> None:
    assert main(["status"]) == 0

