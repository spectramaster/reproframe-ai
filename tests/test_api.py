from fastapi.testclient import TestClient

from reproframe.api import app
from reproframe.cli import sample_brief


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_run() -> None:
    response = TestClient(app).post("/api/runs", json=sample_brief().model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

