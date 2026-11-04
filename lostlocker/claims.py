"""Claiming a found item: the owner asks, the finder approves or declines."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, g, redirect, request, url_for

from . import notifications
from .auth import login_required
from .db import get_db
from .items import DEFAULT_QUESTION, manageable_item

bp = Blueprint("claims", __name__)

MAX_ANSWER = 500


@bp.post("/items/<int:item_id>/claim")
@login_required
def create(item_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT i.item_id, i.status, i.reported_as, i.submitted_by_user, i.verify_question,"
        " u.email AS finder_email, u.name AS finder_name"
        " FROM item i JOIN users u ON u.user_id = i.submitted_by_user WHERE i.item_id = %s",
        (item_id,),
    )
    item = cur.fetchone()
    if item is None or item["reported_as"] != "Found":
        abort(404)
    if item["submitted_by_user"] == g.user["user_id"]:
        flash("You turned this in, so there's nothing to claim.", "error")
        return redirect(url_for("items.detail", item_id=item_id))
    if item["status"] != "Found":
        flash("This item has already been returned to its owner.", "error")
        return redirect(url_for("items.detail", item_id=item_id))

    answer = request.form.get("answer", "").strip()
    if not answer or len(answer) > MAX_ANSWER:
        flash(f"Please answer the question (up to {MAX_ANSWER} characters).", "error")
        return redirect(url_for("items.detail", item_id=item_id) + "#claim")

    cur.execute(
        "INSERT INTO claims (item_id, claimant_id, answer) VALUES (%s, %s, %s)"
        " ON CONFLICT (item_id, claimant_id) DO NOTHING RETURNING claim_id",
        (item_id, g.user["user_id"], answer),
    )
    created = cur.fetchone()
    db.commit()
    if created is None:
        flash("You've already sent a claim for this item.", "error")
    else:
        link = f"{current_app.config['BASE_URL']}/items/{item_id}"
        notifications.send_email(
            current_app.config,
            item["finder_email"],
            "Someone thinks the item you turned in is theirs",
            f"Hi {item['finder_name']},\n\n{g.user['name']} says this is theirs.\n"
            f"Question: {item['verify_question'] or DEFAULT_QUESTION}\nAnswer: {answer}\n\n"
            f"Review the claim: {link}\n\nLost Locker",
        )
        flash("Claim sent! The person who found it will review your answer.", "success")
    return redirect(url_for("items.detail", item_id=item_id))


@bp.post("/claims/<int:claim_id>/<decision>")
@login_required
def decide(claim_id: int, decision: str):
    if decision not in ("approve", "decline"):
        abort(404)
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT c.claim_id, c.item_id, c.status, u.email, u.name"
        " FROM claims c JOIN users u ON u.user_id = c.claimant_id WHERE c.claim_id = %s",
        (claim_id,),
    )
    claim = cur.fetchone()
    if claim is None:
        abort(404)
    manageable_item(cur, claim["item_id"])  # 404 unless you own the item (or are an admin)

    if claim["status"] != "pending":
        flash("That claim was already decided.", "error")
        return redirect(url_for("items.detail", item_id=claim["item_id"]))

    status = "approved" if decision == "approve" else "declined"
    cur.execute(
        "UPDATE claims SET status = %s, decided_at = now() WHERE claim_id = %s", (status, claim_id)
    )
    db.commit()

    link = f"{current_app.config['BASE_URL']}/items/{claim['item_id']}"
    if status == "approved":
        notifications.send_email(
            current_app.config,
            claim["email"],
            "Your claim was approved",
            f"Hi {claim['name']},\n\nGood news. Your claim was approved. Open the link to see how "
            f"to get your item back:\n{link}\n\nLost Locker",
        )
        flash(f"Approved. {claim['name']} can now see how to reach you.", "success")
    else:
        notifications.send_email(
            current_app.config,
            claim["email"],
            "Your claim wasn't approved",
            f"Hi {claim['name']},\n\nThe finder couldn't confirm this item is yours, so the claim "
            f"was declined. You can still look through other found items:\n"
            f"{current_app.config['BASE_URL']}/browse/\n\nLost Locker",
        )
        flash("Claim declined.", "success")
    return redirect(url_for("items.detail", item_id=claim["item_id"]))
