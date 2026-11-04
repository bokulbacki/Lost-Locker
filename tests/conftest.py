"""Test fixtures. Uses TEST_DATABASE_URL if set (CI), otherwise an embedded PostgreSQL."""

from __future__ import annotations

import io
import os
import re
import tempfile

import psycopg2
import pytest
from PIL import Image

from lostlocker import create_app, db


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        yield url
        return
    import pgserver

    with tempfile.TemporaryDirectory() as tmp:
        server = pgserver.get_server(tmp, cleanup_mode="stop")
        try:
            yield server.get_uri()
        finally:
            server.cleanup()


@pytest.fixture(scope="session")
def migrated_url(database_url):
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    with conn.cursor() as cur:  # start from a clean slate if reusing a database
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.close()
    db.run_migrations(database_url)
    return database_url


@pytest.fixture
def app(migrated_url, tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": migrated_url,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )
    yield app
    db.close_pool(app)
    conn = psycopg2.connect(migrated_url)
    conn.autocommit = True
    with conn.cursor() as cur:  # reset user data between tests, keep reference data
        cur.execute("TRUNCATE users, item, item_detail, matches RESTART IDENTITY CASCADE")
    conn.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def outbox(app, monkeypatch):
    """Capture emails instead of sending them."""
    sent: list[dict] = []

    def fake_send(_config, to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("lostlocker.notifications.send_email", fake_send)
    return sent


def register(client, email="alice@example.com", name="Alice", password="correct horse"):  # noqa: S107
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def login(app):
    """Return a function that makes a fresh logged-in client for the given email."""

    def make(email="alice@example.com", name="Alice"):
        c = app.test_client()
        assert register(c, email=email, name=name).status_code == 302
        return c

    return make


@pytest.fixture
def alice(login):
    return login("alice@example.com", "Alice")


@pytest.fixture
def bob(login):
    return login("bob@example.com", "Bob")


def attribute_id(app, group: str, value: str) -> int:
    with app.app_context():
        cur = db.get_db().cursor()
        cur.execute(
            "SELECT attributetype_id FROM attributetype WHERE attributetype = %s"
            " AND description = %s",
            (group, value),
        )
        return cur.fetchone()["attributetype_id"]


def png_bytes(size=(20, 10), color="red") -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def item_id_from(response) -> int:
    match = re.search(r"/items/(\d+)", response.headers["Location"])
    assert match, response.headers.get("Location")
    return int(match.group(1))


def report(app, client, kind, itemtype_id, attrs=None, **extra):
    """Submit a lost/found form. `attrs` maps group -> value text, e.g. {"Brand": "Nike"}."""
    data = {"itemtype_id": str(itemtype_id)}
    for group, value in (attrs or {}).items():
        data[f"attr:{group}"] = str(attribute_id(app, group, value))
    data.update(extra)
    path = "/lostitem/" if kind == "Lost" else "/foundItem/"
    return client.post(path, data=data, content_type="multipart/form-data")
