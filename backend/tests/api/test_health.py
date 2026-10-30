"""API health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Dependency Intelligence" in data["service"]
    assert data["checks"]["database"] is True


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["api"] == "/api/v1"
