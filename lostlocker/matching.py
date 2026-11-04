"""Matching lost reports to found reports.

A lost report and a found report are only compared when they have the same item type. The score
is the sum of a weight for every attribute they share. Vague values ("Other", "Other/Unknown")
never count. Books are compared by title instead. A pair is reported when its score reaches
MATCH_MIN_SCORE (default 1.5), so for example a shared brand alone is enough, but a shared
colour and location alone are not.
"""

from __future__ import annotations

import re

WEIGHTS = {
    "ClothingType": 2.0,
    "Model": 2.0,
    "Brand": 1.5,
    "Color": 1.0,
    "Size": 0.5,
    "Stickers": 0.5,
    "Cap Type": 0.5,
    "Location": 0.25,
}
TITLE_EXACT = 3.0
TITLE_PARTIAL = 2.0
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def is_vague(value: str) -> bool:
    return value.startswith("Other")


def normalize_title(title: str | None) -> str:
    return _NON_ALNUM.sub(" ", (title or "").casefold()).strip()


def title_score(a: str | None, b: str | None) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return TITLE_EXACT
    if na in nb or nb in na:
        return TITLE_PARTIAL
    return 0.0


def find_matches(cur, item_id: int, min_score: float) -> list[tuple[int, float]]:
    """Open reports of the opposite kind that resemble this one: [(item_id, score)], best first."""
    cur.execute("SELECT status, itemtype_id, book_title FROM item WHERE item_id = %s", (item_id,))
    item = cur.fetchone()
    if item is None or item["status"] not in ("Lost", "Found"):
        return []
    other_status = "Found" if item["status"] == "Lost" else "Lost"

    scores: dict[int, float] = {}
    cur.execute(
        "SELECT o.item_id, a.attributetype, a.description"
        " FROM item o"
        " JOIN item_detail od ON od.item_id = o.item_id"
        " JOIN item_detail md ON md.attributetype_id = od.attributetype_id AND md.item_id = %s"
        " JOIN attributetype a ON a.attributetype_id = od.attributetype_id"
        " WHERE o.status = %s AND o.itemtype_id = %s AND o.item_id <> %s",
        (item_id, other_status, item["itemtype_id"], item_id),
    )
    for row in cur.fetchall():
        if is_vague(row["description"]):
            continue
        weight = WEIGHTS.get(row["attributetype"], 0.0)
        scores[row["item_id"]] = scores.get(row["item_id"], 0.0) + weight

    if item["book_title"]:
        cur.execute(
            "SELECT item_id, book_title FROM item"
            " WHERE status = %s AND itemtype_id = %s AND item_id <> %s AND book_title IS NOT NULL",
            (other_status, item["itemtype_id"], item_id),
        )
        for row in cur.fetchall():
            bonus = title_score(item["book_title"], row["book_title"])
            if bonus:
                scores[row["item_id"]] = scores.get(row["item_id"], 0.0) + bonus

    ranked = [(oid, s) for oid, s in scores.items() if s >= min_score]
    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
    return ranked


def record_matches(cur, item_id: int, min_score: float) -> list[int]:
    """Store matches for a newly reported item. Returns the ids of matches that are new."""
    cur.execute("SELECT status FROM item WHERE item_id = %s", (item_id,))
    row = cur.fetchone()
    if row is None:
        return []
    new_ids: list[int] = []
    for other_id, score in find_matches(cur, item_id, min_score):
        lost_id, found_id = (item_id, other_id) if row["status"] == "Lost" else (other_id, item_id)
        cur.execute(
            "INSERT INTO matches (lost_item_id, found_item_id, score) VALUES (%s, %s, %s)"
            " ON CONFLICT (lost_item_id, found_item_id) DO NOTHING RETURNING match_id",
            (lost_id, found_id, score),
        )
        created = cur.fetchone()
        if created:
            new_ids.append(created["match_id"])
    return new_ids
