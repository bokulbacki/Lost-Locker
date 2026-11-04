"""Reference data: item types and the attribute values each type allows."""

from __future__ import annotations

import re

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

# Shown next to the item type name (decorative: the name is always written out too).
ICONS = {
    "Clothing": "\U0001f455",
    "Bottle": "\U0001f964",
    "Device": "\U0001f4f1",
    "Backpack/Bag/Purse": "\U0001f392",
    "Book": "\U0001f4da",
}

# Where a finder can say the item is right now.
HELD_OPTIONS = [
    "I have it and can meet up",
    "I left it at the lost & found desk",
    "I left it where I found it",
]

CHIP_MAX_OPTIONS = 8


def icon_for(itemtype: str) -> str:
    return ICONS.get(itemtype, "\U0001f4e6")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def label_for(group: str) -> str:
    return GROUP_LABELS.get(group, group)


def group_rank(group: str) -> int:
    """Position of an attribute group in the form (unknown groups go last)."""
    return GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER)


def widget_for(group: str, option_count: int) -> str:
    """How a group is shown on the form: color swatches, tap-able chips, or a dropdown."""
    if group == "Color":
        return "swatch"
    if group != "Location" and option_count <= CHIP_MAX_OPTIONS:
        return "chips"
    return "select"


def describe(item: dict) -> str:
    """A short human name for an item, e.g. "Blue Hydro Flask Bottle" or "“Dune”"."""
    if item.get("book_title"):
        return f"“{item['book_title']}”"
    by_group = {
        d["group"]: d["value"] for d in item["details"] if not d["value"].startswith("Other")
    }
    kind = by_group.get("Model") or by_group.get("ClothingType")
    words = [by_group.get("Color"), by_group.get("Brand"), kind or item["itemtype"]]
    return " ".join(w for w in words if w)


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
        for option in options:
            option["slug"] = slug(option["value"])

    return {name: groups[name] for name in sorted(groups, key=lambda n: (group_rank(n), n))}
