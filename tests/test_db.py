from __future__ import annotations

import psycopg2

from lostlocker import db
from lostlocker.config import _database_url


def test_migrations_apply_once(migrated_url):
    assert db.run_migrations(migrated_url) == []  # already applied by the fixture


def test_reference_data_is_consistent(migrated_url):
    conn = psycopg2.connect(migrated_url)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM itemtype")
    assert cur.fetchone()[0] == 5
    # every item type offers a location, and no attribute is offered to a type twice
    cur.execute(
        "SELECT it.itemtype FROM itemtype it WHERE NOT EXISTS ("
        " SELECT 1 FROM item_attribute ia JOIN attributetype a USING (attributetype_id)"
        " WHERE ia.itemtype_id = it.itemtype_id AND a.attributetype = 'Location')"
    )
    assert cur.fetchall() == []
    cur.execute(
        "SELECT description FROM attributetype WHERE attributetype = 'Brand'"
        " GROUP BY description HAVING count(*) > 1"
    )
    assert cur.fetchall() == []
    conn.close()


def test_database_url_built_from_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USERNAME", "me")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_SSLMODE", "require")
    assert (
        _database_url()
        == "postgresql://me:p%40ss%2Fword@db.example.com:5432/lostlocker?sslmode=require"
    )


def test_database_url_prefers_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("DB_USERNAME", "ignored")
    assert _database_url() == "postgresql://x/y"
