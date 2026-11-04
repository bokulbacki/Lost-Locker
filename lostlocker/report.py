"""Reporting a lost or found item (two shared, step-by-step forms)."""

from __future__ import annotations

from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from . import catalog
from .auth import login_required
from .db import get_db
from .matching import record_matches
from .notifications import notify_matches
from .uploads import UploadError, delete_image, save_image

bp = Blueprint("report", __name__)

MAX_NOTES = 500
MAX_TITLE = 200
MAX_QUESTION = 200
MAX_DAYS_BACK = 365


def parse_date(raw: str, today: date | None = None) -> tuple[date | None, str | None]:
    """Parse a YYYY-MM-DD date that is not in the future. Blank means today."""
    today = today or date.today()
    raw = (raw or "").strip()
    if not raw:
        return today, None
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        return None, "Please choose a valid date."
    if value > today:
        return None, "The date can't be in the future."
    if value < today - timedelta(days=MAX_DAYS_BACK):
        return None, "That date is more than a year ago."
    return value, None


def _location_id(cur, raw: str | None) -> int | None:
    """Resolve a `?loc=` value (an id or a place name, e.g. from a QR code) to a location id."""
    raw = (raw or "").strip()
    if not raw:
        return None
    cur.execute(
        "SELECT attributetype_id AS id FROM attributetype WHERE attributetype = 'Location'"
        " AND (attributetype_id::text = %s OR lower(description) = lower(%s))",
        (raw, raw),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _parse(cur, itemtype: dict, form, kind: str):
    """Validate the submitted details. Returns (clean, selected, errors)."""
    groups = catalog.allowed_attributes(cur, itemtype["itemtype_id"])
    errors: list[tuple[str, str]] = []  # (field id, message)
    selected: dict[str, int] = {}
    for group, options in groups.items():
        raw = form.get(f"attr:{group}", "").strip()
        if not raw:
            continue
        if raw not in {str(o["id"]) for o in options}:
            label = catalog.label_for(group).lower()
            errors.append(
                (
                    f"attr-{catalog.slug(group)}",
                    f"Please pick one of the listed options for {label}.",
                )
            )
            continue
        selected[group] = int(raw)

    title = form.get("book_title", "").strip() if itemtype["requires_title"] else ""
    if len(title) > MAX_TITLE:
        errors.append(("book_title", f"The title must be {MAX_TITLE} characters or fewer."))
    notes = form.get("notes", "").strip()
    if len(notes) > MAX_NOTES:
        errors.append(("notes", f"Notes must be {MAX_NOTES} characters or fewer."))

    happened_on, date_error = parse_date(form.get("happened_on", ""))
    if date_error:
        errors.append(("happened_on", date_error))

    held_at = verify_question = None
    if kind == "Found":
        held_at = form.get("held_at", "").strip() or None
        if held_at and held_at not in catalog.HELD_OPTIONS:
            errors.append(("held_at", "Please choose where the item is now."))
        verify_question = form.get("verify_question", "").strip() or None
        if verify_question and len(verify_question) > MAX_QUESTION:
            errors.append(
                ("verify_question", f"The question must be {MAX_QUESTION} characters or fewer.")
            )

    if not errors and not [g_ for g_ in selected if g_ != "Location"] and not title:
        first = next(iter(groups), "")
        errors.append(
            (
                f"attr-{catalog.slug(first)}" if first else "notes",
                "Pick at least one detail about the item (besides where it was).",
            )
        )
    clean = {
        "attribute_ids": list(selected.values()),
        "title": title or None,
        "notes": notes or None,
        "happened_on": happened_on,
        "held_at": held_at,
        "verify_question": verify_question,
    }
    return clean, selected, errors


def _flash_result(kind: str, new_matches: list[int]) -> None:
    if kind == "Found":
        flash("Thank you for turning this in! It's now listed so its owner can find it.", "success")
    elif new_matches:
        n = len(new_matches)
        flash(
            f"Saved. We already found {n} possible match{'es' if n != 1 else ''} below.",
            "success",
        )
    else:
        flash("Saved. We'll email you the moment something similar is turned in.", "success")


def _report(kind: str):
    db = get_db()
    cur = db.cursor()
    types = catalog.item_types(cur)
    by_id = {t["itemtype_id"]: t for t in types}
    endpoint = "report.lost" if kind == "Lost" else "report.found"

    source = request.form if request.method == "POST" else request.args
    itemtype = by_id.get(
        source.get("itemtype_id" if request.method == "POST" else "type", type=int)
    )
    if request.method == "POST" and itemtype is None:
        abort(400)

    context = {
        "kind": kind,
        "endpoint": endpoint,
        "types": [dict(t, icon=catalog.icon_for(t["itemtype"])) for t in types],
        "itemtype": itemtype,
        "today": date.today().isoformat(),
        "held_options": catalog.HELD_OPTIONS,
    }
    if itemtype is None:
        return render_template("report.html", **context)

    groups = catalog.allowed_attributes(cur, itemtype["itemtype_id"])
    context["groups"] = [
        {
            "name": name,
            "label": catalog.label_for(name),
            "slug": catalog.slug(name),
            "widget": catalog.widget_for(name, len(options)),
            "options": options,
        }
        for name, options in groups.items()
    ]
    context["icon"] = catalog.icon_for(itemtype["itemtype"])

    if request.method == "GET":
        selected = {}
        loc_id = _location_id(cur, request.args.get("loc"))
        if loc_id:
            selected["Location"] = loc_id
        return render_template("report.html", selected=selected, form=request.args, **context)

    clean, selected, errors = _parse(cur, itemtype, request.form, kind)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    image_name = None
    if not errors:
        try:
            image_name = save_image(request.files.get("image-upload"), upload_folder)
        except UploadError as exc:
            errors.append(("image-upload", str(exc)))
    if errors:
        return (
            render_template(
                "report.html", selected=selected, form=request.form, errors=errors, **context
            ),
            400,
        )

    try:
        cur.execute(
            "INSERT INTO item (itemtype_id, status, reported_as, book_title, notes, image_filename,"
            " submitted_by_user, happened_on, held_at, verify_question)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING item_id",
            (
                itemtype["itemtype_id"],
                kind,
                kind,
                clean["title"],
                clean["notes"],
                image_name,
                g.user["user_id"],
                clean["happened_on"],
                clean["held_at"],
                clean["verify_question"],
            ),
        )
        item_id = cur.fetchone()["item_id"]
        cur.executemany(
            "INSERT INTO item_detail (item_id, attributetype_id) VALUES (%s, %s)",
            [(item_id, attr_id) for attr_id in clean["attribute_ids"]],
        )
        new_matches = record_matches(cur, item_id, current_app.config["MATCH_MIN_SCORE"])
        db.commit()
    except Exception:
        db.rollback()
        delete_image(upload_folder, image_name)
        raise

    if kind == "Found":
        notify_matches(current_app.config, db, new_matches)
    _flash_result(kind, new_matches)
    return redirect(url_for("items.detail", item_id=item_id))


@bp.route("/lostitem/", methods=("GET", "POST"))
@login_required
def lost():
    return _report("Lost")


@bp.route("/foundItem/", methods=("GET", "POST"))
@login_required
def found():
    return _report("Found")
