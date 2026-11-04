"""Pages for the dashboard, browsing, one item, and managing your own reports."""

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
from .uploads import delete_image, is_stored_name

bp = Blueprint("items", __name__)

_ITEM_SELECT = (
    "SELECT i.item_id, i.status, i.reported_as, i.itemtype_id, it.itemtype, i.book_title,"
    " i.notes, i.image_filename, i.submitted_by_user, i.date_reported, i.happened_on,"
    " i.held_at, i.verify_question,"
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
        row["name"] = catalog.describe(row)
    return rows


def can_manage(item) -> bool:
    return bool(g.user and (g.user["is_admin"] or item["submitted_by_user"] == g.user["user_id"]))


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _page_number() -> int:
    return max(request.args.get("page", 1, type=int) or 1, 1)


def _counts(cur, sql: str, item_ids: list[int]) -> dict[int, int]:
    """Run a `SELECT item_id, count(*) AS n ... = ANY(%s) GROUP BY item_id` query."""
    if not item_ids:
        return {}
    cur.execute(sql, (item_ids,))
    return {row["item_id"]: row["n"] for row in cur.fetchall()}


def _match_counts(cur, lost_ids: list[int]) -> dict[int, int]:
    return _counts(
        cur,
        "SELECT m.lost_item_id AS item_id, count(*) AS n FROM matches m"
        " JOIN item f ON f.item_id = m.found_item_id AND f.status = 'Found'"
        " WHERE m.lost_item_id = ANY(%s) GROUP BY m.lost_item_id",
        lost_ids,
    )


def _pending_claim_counts(cur, found_ids: list[int]) -> dict[int, int]:
    return _counts(
        cur,
        "SELECT item_id, count(*) AS n FROM claims"
        " WHERE status = 'pending' AND item_id = ANY(%s) GROUP BY item_id",
        found_ids,
    )


# --------------------------------------------------------------------------- home / browse


@bp.route("/")
def home():
    cur = get_db().cursor()
    if g.user is None:
        cur.execute("SELECT count(*) AS n FROM item WHERE status = 'Found'")
        return render_template("landing.html", waiting=cur.fetchone()["n"])

    user_id = g.user["user_id"]
    mine = query_items(
        cur, "i.submitted_by_user = %s AND i.status IN ('Lost', 'Found')", (user_id,)
    )
    lost_ids = [i["item_id"] for i in mine if i["status"] == "Lost"]
    found_ids = [i["item_id"] for i in mine if i["status"] == "Found"]
    match_counts = _match_counts(cur, lost_ids)
    claim_counts = _pending_claim_counts(cur, found_ids)

    attention = []
    for item in mine:
        if item["status"] == "Found" and claim_counts.get(item["item_id"]):
            n = claim_counts[item["item_id"]]
            attention.append(
                {
                    "item": item,
                    "text": f"{n} {'person thinks' if n == 1 else 'people think'} "
                    f"this is theirs. Review {'the claim' if n == 1 else 'the claims'}.",
                    "action": "Review",
                }
            )
        elif item["status"] == "Lost" and match_counts.get(item["item_id"]):
            n = match_counts[item["item_id"]]
            attention.append(
                {
                    "item": item,
                    "text": f"{n} possible {'match' if n == 1 else 'matches'} turned in. "
                    "Is one of them yours?",
                    "action": "Take a look",
                }
            )

    cur.execute(
        "SELECT c.claim_id, c.status, c.item_id FROM claims c"
        " WHERE c.claimant_id = %s AND c.status <> 'declined' ORDER BY c.created_at DESC",
        (user_id,),
    )
    my_claims = cur.fetchall()
    approved = [c for c in my_claims if c["status"] == "approved"]
    waiting_on = [c for c in my_claims if c["status"] == "pending"]

    cur.execute("SELECT count(*) AS n FROM item WHERE status = 'Found'")
    return render_template(
        "dashboard.html",
        attention=attention,
        approved=approved,
        waiting_on=waiting_on,
        mine_count=len(mine),
        waiting=cur.fetchone()["n"],
    )


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
    match_counts = _match_counts(cur, [i["item_id"] for i in items if i["status"] == "Lost"])
    claim_counts = _pending_claim_counts(
        cur, [i["item_id"] for i in items if i["status"] == "Found"]
    )
    for item in items:
        item["badge_note"] = _badge_note(item, match_counts, claim_counts)
    sections = [
        ("Still looking", [i for i in items if i["status"] == "Lost"]),
        ("Turned in, waiting for an owner", [i for i in items if i["status"] == "Found"]),
        ("Back with their owner", [i for i in items if i["status"] == "Returned"]),
    ]
    return render_template("my_items.html", sections=sections, total=len(items))


def _badge_note(item, match_counts, claim_counts) -> str:
    if item["status"] == "Lost" and (n := match_counts.get(item["item_id"])):
        return f"{n} possible {'match' if n == 1 else 'matches'}"
    if item["status"] == "Found" and (n := claim_counts.get(item["item_id"])):
        return f"{n} {'claim' if n == 1 else 'claims'} to review"
    return ""


# --------------------------------------------------------------------------- one item


def get_visible_item(cur, item_id: int):
    items = query_items(cur, "i.item_id = %s", (item_id,))
    if not items:
        abort(404)
    item = items[0]
    # Lost reports are private to their owner (and admins). Found items are public to members.
    if item["reported_as"] == "Lost" and not can_manage(item):
        abort(404)
    return item


def progress_steps(item, *, has_matches: bool, has_claims: bool, approved: bool) -> list[dict]:
    """The stages a report moves through, each marked done / current / upcoming."""
    if item["reported_as"] == "Lost":
        names = ["Reported", "Watching for matches", "Possible match", "Back with you"]
        if item["status"] == "Returned":
            current = 3
        elif has_matches:
            current = 2
        else:
            current = 1
    else:
        names = ["Listed", "Claim received", "Owner verified", "Returned"]
        if item["status"] == "Returned":
            current = 3
        elif approved:
            current = 2
        elif has_claims:
            current = 1
        else:
            current = 0
    done_through = current if item["status"] == "Returned" else current - 1
    steps = []
    for index, name in enumerate(names):
        if index <= done_through:
            state = "done"
        elif index == current:
            state = "current"
        else:
            state = "todo"
        steps.append({"name": name, "state": state})
    return steps


@bp.route("/items/<int:item_id>")
@login_required
def detail(item_id: int):
    cur = get_db().cursor()
    item = get_visible_item(cur, item_id)
    manage = can_manage(item)
    matches = []
    claims = []
    my_claim = None
    finder = None

    if item["reported_as"] == "Lost" and item["status"] == "Lost":
        scores = {}
        cur.execute("SELECT found_item_id, score FROM matches WHERE lost_item_id = %s", (item_id,))
        for row in cur.fetchall():
            scores[row["found_item_id"]] = float(row["score"])
        if scores:
            found = query_items(cur, "i.item_id = ANY(%s) AND i.status = 'Found'", (list(scores),))
            matches = sorted(found, key=lambda f: -scores[f["item_id"]])

    if item["reported_as"] == "Found":
        cur.execute(
            "SELECT c.claim_id, c.claimant_id, c.answer, c.status, c.created_at, u.name, u.email"
            " FROM claims c JOIN users u ON u.user_id = c.claimant_id"
            " WHERE c.item_id = %s ORDER BY c.created_at",
            (item_id,),
        )
        all_claims = cur.fetchall()
        if manage:
            claims = all_claims
        else:
            my_claim = next((c for c in all_claims if c["claimant_id"] == g.user["user_id"]), None)
            if my_claim and my_claim["status"] == "approved":
                cur.execute(
                    "SELECT name, email FROM users WHERE user_id = %s", (item["submitted_by_user"],)
                )
                finder = cur.fetchone()
        has_claims = bool(all_claims)
        approved = any(c["status"] == "approved" for c in all_claims)
    else:
        has_claims = approved = False

    steps = (
        progress_steps(item, has_matches=bool(matches), has_claims=has_claims, approved=approved)
        if manage
        else None
    )
    return render_template(
        "item.html",
        item=item,
        matches=matches,
        claims=claims,
        my_claim=my_claim,
        finder=finder,
        steps=steps,
        can_manage=manage,
        question=item["verify_question"] or DEFAULT_QUESTION,
        claim_instructions=current_app.config["CLAIM_INSTRUCTIONS"],
    )


DEFAULT_QUESTION = "Tell us something about it that isn't in the photo or listing."


def manageable_item(cur, item_id: int):
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
    item = manageable_item(cur, item_id)
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
    manageable_item(cur, item_id)
    cur.execute(
        "UPDATE item SET status = 'Returned' WHERE item_id = %s AND status IN ('Lost', 'Found')",
        (item_id,),
    )
    cur.execute(
        "UPDATE claims SET status = 'declined', decided_at = now()"
        " WHERE item_id = %s AND status = 'pending'",
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
