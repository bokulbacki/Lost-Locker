from __future__ import annotations

import pytest

from lostlocker import create_app
from lostlocker.auth import safe_next

from .conftest import register


def test_pages_require_login(client):
    for path in ("/", "/browse/", "/my-items/", "/lostitem/", "/foundItem/", "/items/1"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_api_and_images_not_leaked_without_login(client):
    assert client.get("/images/" + "a" * 32 + ".jpg").status_code == 302


def test_register_login_logout(app):
    c = app.test_client()
    assert register(c).status_code == 302
    assert c.get("/").status_code == 200
    assert c.post("/logout").status_code == 302
    assert c.get("/").status_code == 302

    response = c.post("/login", data={"email": "ALICE@example.com", "password": "correct horse"})
    assert response.status_code == 302
    assert c.get("/").status_code == 200


def test_login_rejects_bad_credentials_with_one_message(client):
    register(client)
    client.post("/logout")
    wrong_password = client.post("/login", data={"email": "alice@example.com", "password": "nope"})
    unknown_user = client.post("/login", data={"email": "who@example.com", "password": "nope"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert b"Invalid email and/or password" in wrong_password.data
    assert b"Invalid email and/or password" in unknown_user.data


def test_register_validation(client):
    response = client.post("/register", data={"name": "", "email": "bad", "password": "short"})
    assert response.status_code == 400
    for text in (b"your name", b"valid email", b"at least 8"):
        assert text in response.data


def test_register_duplicate_email(client, app):
    register(client)
    other = app.test_client()
    response = register(other)
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_passwords_are_hashed(app, client):
    from lostlocker import db

    register(client, password="correct horse")
    with app.app_context():
        cur = db.get_db().cursor()
        cur.execute("SELECT password_hash FROM users")
        stored = cur.fetchone()["password_hash"]
    assert "correct horse" not in stored
    assert stored.startswith(("scrypt:", "pbkdf2:"))


def test_email_domain_restriction(migrated_url, tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": migrated_url,
            "UPLOAD_FOLDER": str(tmp_path),
            "WTF_CSRF_ENABLED": False,
            "ALLOWED_EMAIL_DOMAIN": "sandiego.edu",
        }
    )
    c = app.test_client()
    assert register(c, email="a@gmail.com").status_code == 400
    assert register(c, email="a@sandiego.edu").status_code == 302


@pytest.mark.parametrize(
    "target, expected",
    [
        ("/browse/?page=2", "/browse/?page=2"),
        ("https://evil.example/", "/"),
        ("//evil.example/", "/"),
        ("javascript:alert(1)", "/"),
        ("/\\evil.example", "/"),
        ("", "/"),
        (None, "/"),
    ],
)
def test_safe_next(app, target, expected):
    with app.test_request_context():
        assert safe_next(target) == expected


def test_login_redirects_back_only_to_local_paths(client):
    register(client)
    client.post("/logout")
    response = client.post(
        "/login",
        data={
            "email": "alice@example.com",
            "password": "correct horse",
            "next": "https://evil.example",
        },
    )
    assert response.headers["Location"] == "/"


def test_csrf_enforced(migrated_url, tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": migrated_url,
            "UPLOAD_FOLDER": str(tmp_path),
            "WTF_CSRF_ENABLED": True,
        }
    )
    response = app.test_client().post(
        "/register", data={"name": "x", "email": "x@example.com", "password": "password1"}
    )
    assert response.status_code == 400
    assert b"expired" in response.data


def test_security_headers(client):
    response = client.get("/login")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_secret_key_required_outside_debug_and_testing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "0")  # a developer's .env may turn debug on
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()
