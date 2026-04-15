from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_index_returns_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hello World from FastAPI" in response.text


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_serves_exported_frontend_files(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend_dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    (frontend_dist / "asset.js").write_text("console.log('ok')", encoding="utf-8")

    test_client = TestClient(create_app(frontend_dist))

    home_response = test_client.get("/")
    assert home_response.status_code == 200
    assert "Kanban Studio" in home_response.text

    asset_response = test_client.get("/asset.js")
    assert asset_response.status_code == 200
    assert "console.log('ok')" in asset_response.text
