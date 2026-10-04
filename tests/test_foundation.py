"""Phase 0 foundation tests: factory, routing, error handling, health check."""

from __future__ import annotations


def test_app_factory_creates_app(app):
    assert app is not None
    assert app.config["TESTING"] is True


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"PoshanSathi" in response.data


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["app"] == "PoshanSathi"


def test_unknown_route_returns_404(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert b"404" in response.data


def test_static_css_served(client):
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert b"PoshanSathi" in response.data
