"""API smoke tests that do not require Postgres."""

from fastapi.testclient import TestClient

from api.app.main import app
from gitpulse.topics import TOPICS

client = TestClient(app)


def test_topics_endpoint() -> None:
    response = client.get("/api/topics")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == len(TOPICS)
    assert payload[0]["slug"]
    assert payload[0]["label"]


def test_unknown_series_404() -> None:
    response = client.get("/api/series/not-a-real-topic")
    assert response.status_code == 404
