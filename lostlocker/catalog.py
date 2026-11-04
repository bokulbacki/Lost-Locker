"""Reference data: item types and the attribute values each type allows."""

from __future__ import annotations

# Order the form fields are shown in, and how each group is labelled.
GROUP_ORDER = [
    "ClothingType",
    "Brand",
    "Model",
    "Color",
    "Size",
    "Stickers",
    "Cap Type",
    "Location",
]
GROUP_LABELS = {
    "ClothingType": "Type of clothing",
    "Brand": "Brand",
    "Model": "Model",
    "Color": "Color",
    "Size": "Size",
    "Stickers": "Stickers",
    "Cap Type": "Cap type",
    "Location": "Location",
}
# Groups whose options read best alphabetically (the rest keep their natural id order).
_ALPHABETICAL = {"Brand", "Model", "Color"}


def label_for(group: str) -> str:
    return GROUP_LABELS.get(group, group)


def group_rank(group: str) -> int:
    """Position of an attribute group in the form (unknown groups go last)."""
    return GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER)


def item_types(cur) -> list[dict]:
    cur.execute("SELECT itemtype_id, itemtype, requires_title FROM itemtype ORDER BY itemtype_id")
    return list(cur.fetchall())


def allowed_attributes(cur, itemtype_id: int) -> dict[str, list[dict]]:
    """Attribute options for an item type, as {group: [{"id", "value"}, ...]} in form order."""
    cur.execute(
        "SELECT a.attributetype_id AS id, a.attributetype AS grp, a.description AS value"
        " FROM item_attribute ia"
        " JOIN attributetype a ON a.attributetype_id = ia.attributetype_id"
        " WHERE ia.itemtype_id = %s ORDER BY a.attributetype_id",
        (itemtype_id,),
    )
    groups: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        groups.setdefault(row["grp"], []).append({"id": row["id"], "value": row["value"]})

    for name, options in groups.items():
        if name in _ALPHABETICAL:
            # "Other..." entries go last
            options.sort(key=lambda o: (o["value"].startswith("Other"), o["value"].lower()))

    return {name: groups[name] for name in sorted(groups, key=lambda n: (group_rank(n), n))}
