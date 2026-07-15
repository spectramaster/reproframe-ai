from fastapi.testclient import TestClient

from reproframe.api import app
from reproframe.cli import sample_brief


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_run() -> None:
    client = TestClient(app)
    response = client.post("/api/runs", json=sample_brief().model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    run_id = response.json()["run_id"]

    details = client.get(f"/api/runs/{run_id}")
    assert details.status_code == 200
    assert details.json()["verification"]["valid"] is True

    history = client.get("/api/runs?limit=1")
    assert history.status_code == 200
    assert history.json()[0]["run_id"] == run_id

    bundle = client.get(f"/api/runs/{run_id}/bundle")
    assert bundle.status_code == 200
    assert bundle.headers["content-type"] == "application/zip"

    review = client.post(
        f"/api/runs/{run_id}/review",
        json={"decision": "accepted", "reviewer": "test-reviewer"},
    )
    assert review.status_code == 403
