from fastapi.testclient import TestClient

from app.main import app


def test_healthz_ok():
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
