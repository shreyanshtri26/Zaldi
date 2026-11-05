import pytest

from zaldi import config


@pytest.fixture
def built_frontend(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(config, "FRONTEND_DIST", tmp_path)


def test_client_side_routes_fall_back_to_index(client, built_frontend):
    for path in ("/", "/admin", "/admin/anything"):
        assert b"app" in client.get(path).data


def test_built_assets_are_served(client, built_frontend):
    assert client.get("/assets/app.js").data == b"console.log(1)"


def test_missing_build_returns_a_helpful_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FRONTEND_DIST", tmp_path / "missing")
    response = client.get("/")
    assert response.status_code == 404 and b"npm run build" in response.data
