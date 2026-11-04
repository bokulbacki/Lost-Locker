"""Small read-only JSON API for the reference data behind the report forms."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify

from . import catalog
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/item-types")
def item_types():
    cur = get_db().cursor()
    return jsonify(
        [
            {"id": t["itemtype_id"], "name": t["itemtype"], "requires_title": t["requires_title"]}
            for t in catalog.item_types(cur)
        ]
    )


@bp.get("/item-types/<int:itemtype_id>/attributes")
def attributes(itemtype_id: int):
    cur = get_db().cursor()
    itemtype = next((t for t in catalog.item_types(cur) if t["itemtype_id"] == itemtype_id), None)
    if itemtype is None:
        abort(404)
    groups = catalog.allowed_attributes(cur, itemtype_id)
    return jsonify(
        {
            "id": itemtype["itemtype_id"],
            "name": itemtype["itemtype"],
            "requires_title": itemtype["requires_title"],
            "groups": [
                {"name": name, "label": catalog.label_for(name), "options": options}
                for name, options in groups.items()
            ],
        }
    )
