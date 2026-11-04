"""Pages for reporting lost/found items, browsing, and managing your own reports."""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import catalog
from .auth import login_required
from .db import get_db
from .matching import record_matches
from .notifications import notify_matches
from .uploads import UploadError, delete_image, is_stored_name, save_image

bp = Blueprint("items", __name__)

MAX_NOTES = 500
MAX_TITLE = 200

_ITEM_SELECT = (
    "SELECT i.item_id, i.status, i.reported_as, i.itemtype_id, it.itemtype, i.book_title,"
    " i.notes, i.image_filename, i.submitted_by_user, i.date_reported,"
    " COALESCE(json_agg(json_build_object('group', a.attributetype, 'value', a.description)"
    "   ORDER BY a.attributetype_id) FILTER (WHERE a.attributetype_id IS NOT NULL),"
    "   '[]') AS details"
    " FROM item i"
    " JOIN itemtype it ON it.itemtype_id = i.itemtype_id"
    " LEFT JOIN item_detail d ON d.item_id = i.item_id"
    " LEFT JOIN attributetype a ON a.attributetype_id = d.attributetype_id"
)


def query_items(cur, where: str, params: tuple, limit: int | None = None, offset: int = 0):
    """Items matching `where` (a trusted SQL fragment), each with a `details` list, newest first."""
    sql = (  # noqa: S608 - `where` is always a fixed fragment written in this module
        f"{_ITEM_SELECT} WHERE {where}"
        " GROUP BY i.item_id, it.itemtype_id ORDER BY i.created_at DESC, i.item_id DESC"
    )
    if limit is not None:
        sql += " LIMIT %s OFFSET %s"
        params = (*params, limit, offset)
    cur.execute(sql, params)
    rows = cur.fetchall()
    for row in rows:
        row["details"] = sorted(row["details"], key=lambda d: catalog.group_rank(d["group"]))
        for detail in row["details"]:
            detail["label"] = catalog.label_for(detail["group"])
    return rows


def can_manage(item) -> bool:
    return bool(g.user and (g.user["is_admin"] or item["submitted_by_user"] == g.user["user_id"]))


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _page_number() -> int:
    return max(request.args.get("page", 1, type=int) or 1, 1)


# --------------------------------------------------------------------------- home / browse


@bp.route("/")
@login_required
def home():
    cur = get_db().cursor()
    cur.execute("SELECT count(*) AS n FROM item WHERE status = 'Found'")
    waiting = cur.fetchone()["n"]
    cur.execute(
        "SELECT count(*) AS n FROM item"
        " WHERE submitted_by_user = %s AND status IN ('Lost', 'Found')",
        (g.user["user_id"],),
    )
    mine = cur.fetchone()["n"]
    cur.execute(
        "SELECT count(DISTINCT m.found_item_id) AS n FROM matches m"
        " JOIN item l ON l.item_id = m.lost_item_id AND l.status = 'Lost'"
        " JOIN item f ON f.item_id = m.found_item_id AND f.status = 'Found'"
        " WHERE l.submitted_by_user = %s",
        (g.user["user_id"],),
    )
    possible = cur.fetchone()["n"]
    return render_template("home.html", waiting=waiting, mine=mine, possible=possible)


@bp.route("/browse/")
@login_required
def browse():
    cur = get_db().cursor()
    per_page = current_app.config["ITEMS_PER_PAGE"]
    type_id = request.args.get("type", type=int)
    q = request.args.get("q", "").strip()[:100]

    where, params = ["i.status = 'Found'"], []
    if type_id:
        where.append("i.itemtype_id = %s")
        params.append(type_id)
    if q:
        where.append(
            "(i.book_title ILIKE %s OR i.notes ILIKE %s OR EXISTS ("
            " SELECT 1 FROM item_detail d2 JOIN attributetype a2"
            "  ON a2.attributetype_id = d2.attributetype_id"
            " WHERE d2.item_id = i.item_id AND a2.description ILIKE %s))"
        )
        params.extend([_like(q)] * 3)
    where_sql = " AND ".join(where)

    cur.execute(f"SELECT count(*) AS n FROM item i WHERE {where_sql}", tuple(params))  # noqa: S608
    total = cur.fetchone()["n"]
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(_page_number(), pages)
    items = query_items(cur, where_sql, tuple(params), per_page, (page - 1) * per_page)
    return render_template(
        "browse.html",
        items=items,
        types=catalog.item_types(cur),
        type_id=type_id,
        q=q,
        page=page,
        pages=pages,
        total=total,
    )


@bp.route("/my-items/")
@login_required
def my_items():
    cur = get_db().cursor()
    items = query_items(cur, "i.submitted_by_user = %s", (g.user["user_id"],))
    return render_template("my_items.html", items=items)


# --------------------------------------------------------------------------- reporting


def _parse_report(cur, itemtype: dict, form):
    """Validate the submitted details. Returns (attribute_ids, title, notes, selected, errors)."""
    groups = catalog.allowed_attributes(cur, itemtype["itemtype_id"])
    errors: list[str] = []
    attribute_ids: list[int] = []
    selected: dict[str, int] = {}
    for group, options in groups.items():
        raw = form.get(f"attr:{group}", "").strip()
        if not raw:
            continue
        valid = {str(o["id"]) for o in options}
        if raw not in valid:
            errors.append(f"“{raw}” is not a valid choice for {catalog.label_for(group).lower()}.")
            continue
        attribute_ids.append(int(raw))
        selected[group] = int(raw)

    title = form.get("book_title", "").strip() if itemtype["requires_title"] else ""
    if len(title) > MAX_TITLE:
        errors.append(f"The title must be {MAX_TITLE} characters or fewer.")
    notes = form.get("notes", "").strip()
    if len(notes) > MAX_NOTES:
        errors.append(f"Notes must be {MAX_NOTES} characters or fewer.")

    descriptive = [g_ for g_ in selected if g_ != "Location"]
    if not errors and not descriptive and not title:
        errors.append("Please describe the item with at least one detail besides the location.")
    return attribute_ids, title, notes, selected, errors


def _report(kind: str):
    """Shared handler for the lost (kind='Lost') and found (kind='Found') forms."""
    db = get_db()
    cur = db.cursor()
    types = catalog.item_types(cur)
    by_id = {t["itemtype_id"]: t for t in types}
    endpoint = "items.lost_claim" if kind == "Lost" else "items.found_claim"

    if request.method == "POST":
        itemtype = by_id.get(request.form.get("itemtype_id", type=int))
        if itemtype is None:
            abort(400)
    else:
        itemtype = by_id.get(request.args.get("type", type=int))

    context = {"kind": kind, "endpoint": endpoint, "types": types, "itemtype": itemtype}
    if itemtype is None:
        return render_template("claim.html", **context)

    groups = catalog.allowed_attributes(cur, itemtype["itemtype_id"])
    context["groups"] = [
        {"name": name, "label": catalog.label_for(name), "options": options}
        for name, options in groups.items()
    ]
    if request.method == "GET":
        return render_template("claim.html", selected={}, form=request.args, **context)

    attribute_ids, title, notes, selected, errors = _parse_report(cur, itemtype, request.form)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    image_name = None
    if not errors:
        try:
            image_name = save_image(request.files.get("image-upload"), upload_folder)
        except UploadError as exc:
            errors.append(str(exc))
    if errors:
        return (
            render_template(
                "claim.html", selected=selected, form=request.form, errors=errors, **context
            ),
            400,
        )

    try:
        cur.execute(
            "INSERT INTO item (itemtype_id, status, reported_as, book_title, notes,"
            " image_filename, submitted_by_user) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            " RETURNING item_id",
            (
                itemtype["itemtype_id"],
                kind,
                kind,
                title or None,
                notes or None,
                image_name,
                g.user["user_id"],
            ),
        )
        item_id = cur.fetchone()["item_id"]
        cur.executemany(
            "INSERT INTO item_detail (item_id, attributetype_id) VALUES (%s, %s)",
            [(item_id, attr_id) for attr_id in attribute_ids],
        )
        new_matches = record_matches(cur, item_id, current_app.config["MATCH_MIN_SCORE"])
        db.commit()
    except Exception:
        db.rollback()
        delete_image(upload_folder, image_name)
        raise

    if kind == "Found":
        notify_matches(current_app.config, db, new_matches)
        flash("Thanks for turning this in! It's now listed in the locker.", "success")
    elif new_matches:
        flash(
            f"Your lost item report is saved, and we found {len(new_matches)} possible "
            f"match{'es' if len(new_matches) != 1 else ''}.",
            "success",
        )
    else:
        flash(
            "Your lost item report is saved. We'll email you if something similar is turned in.",
            "success",
        )
    return redirect(url_for("items.detail", item_id=item_id))


@bp.route("/lostitem/", methods=("GET", "POST"))
@login_required
def lost_claim():
    return _report("Lost")


@bp.route("/foundItem/", methods=("GET", "POST"))
@login_required
def found_claim():
    return _report("Found")


# --------------------------------------------------------------------------- one item


def _get_visible_item(cur, item_id: int):
    items = query_items(cur, "i.item_id = %s", (item_id,))
    if not items:
        abort(404)
    item = items[0]
    # Lost reports are private to their owner (and admins). Found items are public to members.
    if item["reported_as"] == "Lost" and not can_manage(item):
        abort(404)
    return item


@bp.route("/items/<int:item_id>")
@login_required
def detail(item_id: int):
    cur = get_db().cursor()
    item = _get_visible_item(cur, item_id)
    matches = []
    if item["reported_as"] == "Lost" and item["status"] == "Lost":
        scores = {}
        cur.execute("SELECT found_item_id, score FROM matches WHERE lost_item_id = %s", (item_id,))
        for row in cur.fetchall():
            scores[row["found_item_id"]] = float(row["score"])
        if scores:
            found = query_items(cur, "i.item_id = ANY(%s) AND i.status = 'Found'", (list(scores),))
            matches = sorted(found, key=lambda f: -scores[f["item_id"]])
    return render_template(
        "item.html",
        item=item,
        matches=matches,
        can_manage=can_manage(item),
        claim_instructions=current_app.config["CLAIM_INSTRUCTIONS"],
    )


def _manageable_item(cur, item_id: int):
    cur.execute(
        "SELECT item_id, status, submitted_by_user, image_filename FROM item WHERE item_id = %s",
        (item_id,),
    )
    item = cur.fetchone()
    if item is None or not can_manage(item):
        abort(404)
    return item


@bp.post("/items/<int:item_id>/delete")
@login_required
def delete(item_id: int):
    db = get_db()
    cur = db.cursor()
    item = _manageable_item(cur, item_id)
    cur.execute("DELETE FROM item WHERE item_id = %s", (item_id,))
    db.commit()
    delete_image(current_app.config["UPLOAD_FOLDER"], item["image_filename"])
    flash("The report was deleted.", "success")
    return redirect(url_for("items.my_items"))


@bp.post("/items/<int:item_id>/returned")
@login_required
def mark_returned(item_id: int):
    db = get_db()
    cur = db.cursor()
    _manageable_item(cur, item_id)
    cur.execute(
        "UPDATE item SET status = 'Returned' WHERE item_id = %s AND status IN ('Lost', 'Found')",
        (item_id,),
    )
    db.commit()
    flash("Marked as returned. It will no longer appear in the locker.", "success")
    return redirect(url_for("items.detail", item_id=item_id))


@bp.route("/images/<filename>")
@login_required
def image(filename: str):
    if not is_stored_name(filename):
        abort(404)
    response = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, max_age=86400)
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
