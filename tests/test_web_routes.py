"""FastAPI shell — public pages render, the OAuth start redirects, and status
routes correctly gate on an authenticated session."""

from fastapi.testclient import TestClient

from volley.web.app import app

client = TestClient(app)


def test_landing_page_ok():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Sign in with Google" in resp.text


def test_privacy_and_tos_pages_ok():
    assert client.get("/privacy").status_code == 200
    assert client.get("/tos").status_code == 200


def test_auth_google_redirects_to_google_consent():
    resp = client.get("/auth/google", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


def test_app_status_requires_session():
    resp = client.get("/app")
    assert resp.status_code == 401


def test_disconnect_requires_session():
    resp = client.post("/disconnect")
    assert resp.status_code == 401


def test_callback_rejects_missing_state():
    resp = client.get("/auth/callback", params={"code": "some-code"})
    assert resp.status_code == 400
