"""Accounts: registration, login/logout and the decorators that protect routes."""

from __future__ import annotations

import functools
import re
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
# Checked when the email is unknown so a login attempt takes the same time either way.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.before_app_request
def load_logged_in_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    cur = get_db().cursor()
    cur.execute("SELECT user_id, email, name, is_admin FROM users WHERE user_id = %s", (user_id,))
    g.user = cur.fetchone()
    if g.user is None:  # account was deleted
        session.clear()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def safe_next(target: str | None) -> str:
    """Only follow `next` to a path on this site (prevents open redirects)."""
    if not target:
        return url_for("items.home")
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return url_for("items.home")
    if "\\" in target:
        return url_for("items.home")
    return target


def _email_allowed(email: str) -> bool:
    domain = current_app.config.get("ALLOWED_EMAIL_DOMAIN", "")
    return not domain or email.endswith("@" + domain.lower())


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        errors = []
        if not name or len(name) > 100:
            errors.append("Please enter your name (100 characters or fewer).")
        if not EMAIL_RE.match(email) or len(email) > 254:
            errors.append("Please enter a valid email address.")
        elif not _email_allowed(email):
            errors.append(
                f"Please use your @{current_app.config['ALLOWED_EMAIL_DOMAIN']} email address."
            )
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Your password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if not errors:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)"
                " ON CONFLICT (email) DO NOTHING RETURNING user_id",
                (email, name, generate_password_hash(password)),
            )
            row = cur.fetchone()
            if row is None:
                db.rollback()
                errors.append("An account with that email already exists. Try logging in.")
            else:
                db.commit()
                session.clear()
                session["user_id"] = row["user_id"]
                flash("Welcome to Lost Locker!", "success")
                return redirect(url_for("items.home"))
        for message in errors:
            flash(message, "error")
        return render_template("register.html", name=name, email=email), 400
    return render_template("register.html", name="", email="")


@bp.route("/login", methods=("GET", "POST"))
def login():
    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        cur = get_db().cursor()
        cur.execute("SELECT user_id, password_hash FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        hash_to_check = user["password_hash"] if user else _DUMMY_HASH
        if check_password_hash(hash_to_check, password) and user:
            session.clear()  # new session on login
            session["user_id"] = user["user_id"]
            return redirect(safe_next(next_url))
        flash("Invalid email and/or password.", "error")
        return render_template("login.html", email=email, next=next_url), 401
    if g.user is not None:
        return redirect(url_for("items.home"))
    return render_template("login.html", email="", next=next_url)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
