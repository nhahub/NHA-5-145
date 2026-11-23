from agent.app import app
from agent.tests.http_client import TestClient


def test_health_reports_service_ready() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agent"}
