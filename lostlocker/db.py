"""Database access: a connection pool, one connection per request, and the migration runner."""

from __future__ import annotations

import threading
from pathlib import Path

import psycopg2
from flask import Flask, current_app, g
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_pool_lock = threading.Lock()
_MIGRATION_LOCK_ID = 727274  # arbitrary; stops two processes migrating at once


def _pool() -> ThreadedConnectionPool:
    pool = current_app.extensions.get("db_pool")
    if pool is None:
        with _pool_lock:
            pool = current_app.extensions.get("db_pool")
            if pool is None:
                url = current_app.config["DATABASE_URL"]
                if not url:
                    raise RuntimeError(
                        "No database configured. Set DATABASE_URL (or DB_USERNAME/DB_PASSWORD/"
                        "DB_HOST/DB_NAME) in the environment or .env file."
                    )
                pool = ThreadedConnectionPool(
                    1, current_app.config["DB_POOL_MAX"], url, cursor_factory=RealDictCursor
                )
                current_app.extensions["db_pool"] = pool
    return pool


def get_db():
    """The connection for this request. Commit explicitly; uncommitted work is rolled back."""
    if "db" not in g:
        g.db = _pool().getconn()
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        try:
            if not conn.closed:
                conn.rollback()
        finally:
            _pool().putconn(conn)


def close_pool(app: Flask) -> None:
    pool = app.extensions.pop("db_pool", None)
    if pool is not None:
        pool.closeall()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)


def run_migrations(dsn: str) -> list[str]:
    """Apply any migrations/*.sql files not yet recorded. All-or-nothing. Returns names applied."""
    applied: list[str] = []
    conn = psycopg2.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_ID,))
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT name FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
    finally:
        conn.close()
    return applied
