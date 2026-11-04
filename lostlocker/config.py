"""Configuration, read from environment variables (and a local .env file in development)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    """DATABASE_URL if set, otherwise built from the DB_* variables the project used before."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("DB_USERNAME")
    if not user:
        return ""
    password = quote(os.getenv("DB_PASSWORD", ""), safe="")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "lostlocker")
    url = f"postgresql://{quote(user, safe='')}:{password}@{host}:{port}/{name}"
    sslmode = os.getenv("DB_SSLMODE")
    return f"{url}?sslmode={sslmode}" if sslmode else url


def load_config() -> dict:
    """Read settings from the environment. Call after load_dotenv()."""
    load_dotenv()
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", ""),
        "DATABASE_URL": _database_url(),
        "DB_POOL_MAX": int(os.getenv("DB_POOL_MAX", "10")),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _flag("SESSION_COOKIE_SECURE"),
        "MAX_CONTENT_LENGTH": 8 * 1024 * 1024,
        "UPLOAD_FOLDER": os.getenv("UPLOAD_FOLDER") or str(ROOT / "instance" / "uploads"),
        "BASE_URL": os.getenv("BASE_URL", "http://localhost:5000").rstrip("/"),
        # e.g. "sandiego.edu" to only allow registration with university addresses
        "ALLOWED_EMAIL_DOMAIN": os.getenv("ALLOWED_EMAIL_DOMAIN", "").strip().lstrip("@"),
        "CLAIM_INSTRUCTIONS": os.getenv(
            "CLAIM_INSTRUCTIONS", "Contact the lost and found desk to claim this item."
        ),
        "MAIL_SERVER": os.getenv("MAIL_SERVER", ""),
        "MAIL_PORT": int(os.getenv("MAIL_PORT", "587")),
        "MAIL_USE_TLS": _flag("MAIL_USE_TLS", True),
        "MAIL_USERNAME": os.getenv("MAIL_USERNAME", ""),
        "MAIL_PASSWORD": os.getenv("MAIL_PASSWORD", ""),
        "MAIL_FROM": os.getenv("MAIL_FROM", "lostlocker@example.com"),
        "MATCH_MIN_SCORE": float(os.getenv("MATCH_MIN_SCORE", "1.5")),
        "ITEMS_PER_PAGE": 12,
    }
