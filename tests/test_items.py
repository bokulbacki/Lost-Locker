from __future__ import annotations

import re

from .conftest import attribute_id, item_id_from, png_bytes, report

CLOTHING, BOTTLE, DEVICE, BAG, BOOK = 1, 2, 3, 4, 5


def test_api_item_types(alice):
    data = alice.get("/api/item-types").get_json()
    assert [t["name"] for t in data] == [
        "Clothing",
        "Bottle",
        "Device",
        "Backpack/Bag/Purse",
        "Book",
    ]
    assert [t["requires_title"] for t in data] == [False, False, False, False, True]


def test_api_attributes_depend_on_item_type(alice):
    def groups(type_id):
        data = alice.get(f"/api/item-types/{type_id}/attributes").get_json()
        return [g["name"] for g in data["groups"]]

    assert "ClothingType" in groups(CLOTHING)
    assert "Model" in groups(DEVICE) and "ClothingType" not in groups(DEVICE)
    assert "Cap Type" in groups(BOTTLE)
    assert "Brand" not in groups(BOOK)
    assert alice.get("/api/item-types/999/attributes").status_code == 404


def test_report_form_shows_options_for_chosen_type(alice):
    html = alice.get("/lostitem/?type=2").get_data(as_text=True)
    assert "Hydro Flask" in html and "Nozzle Lid" in html
    assert "Nike" not in html  # clothing-only brand
    # the type picker is shown when no type is chosen
    assert "Backpack/Bag/Purse" in alice.get("/lostitem/").get_data(as_text=True)


def test_submit_lost_item(app, alice):
    response = report(app, alice, "Lost", CLOTHING, {"Brand": "Nike", "Color": "Black"})
    assert response.status_code == 302
    page = alice.get(response.headers["Location"]).get_data(as_text=True)
    assert "Nike" in page and "Black" in page and "Lost" in page


def test_submit_requires_a_real_detail(app, alice):
    response = report(app, alice, "Lost", CLOTHING, {"Location": "Tram"})
    assert response.status_code == 400
    assert b"at least one detail" in response.data


def test_rejects_value_from_another_item_type(app, alice):
    # "Hydro Flask" is a bottle brand and not offered for clothing
    response = report(app, alice, "Found", CLOTHING, {"Brand": "Hydro Flask"})
    assert response.status_code == 400
    assert b"pick one of the listed options" in response.data


def test_rejects_unknown_item_type(alice):
    assert alice.post("/lostitem/", data={"itemtype_id": "999"}).status_code == 400


def test_book_needs_title_not_attributes(app, alice):
    assert report(app, alice, "Found", BOOK, {}).status_code == 400
    response = report(app, alice, "Found", BOOK, {}, book_title="Dune")
    assert response.status_code == 302
    assert "Dune" in alice.get(response.headers["Location"]).get_data(as_text=True)


def test_sql_injection_attempts_are_inert(app, alice):
    evil = "'; DROP TABLE item; --"
    assert alice.get("/browse/", query_string={"q": evil, "type": "1 OR 1=1"}).status_code == 200
    assert report(app, alice, "Found", BOOK, {}, book_title=evil).status_code == 302
    assert alice.get("/my-items/").status_code == 200  # tables still exist
    assert alice.get("/items/1%20OR%201=1").status_code == 404


def test_browse_shows_only_found_items(app, alice, bob):
    report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"})
    report(app, alice, "Lost", BOTTLE, {"Brand": "Camelbak"})
    html = bob.get("/browse/").get_data(as_text=True)
    assert "Yeti" in html
    assert "Camelbak" not in html


def test_browse_filters_and_paginates(app, alice, bob):
    for _ in range(14):
        report(app, alice, "Found", BAG, {"Brand": "Jansport"})
    report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"})

    assert "Page 1 of 2" in bob.get("/browse/").get_data(as_text=True)
    bottles = bob.get("/browse/", query_string={"type": BOTTLE}).get_data(as_text=True)
    assert "Yeti" in bottles and "Jansport" not in bottles
    search = bob.get("/browse/", query_string={"q": "yeti"}).get_data(as_text=True)
    assert "Yeti" in search and "Jansport" not in search
    assert "1 item" in search
    # a nonsense page number is clamped, a LIKE wildcard is treated literally
    assert bob.get("/browse/?page=999").status_code == 200
    assert "0 items" in bob.get("/browse/", query_string={"q": "%"}).get_data(as_text=True)


def test_lost_reports_are_private(app, alice, bob):
    item_id = item_id_from(report(app, alice, "Lost", DEVICE, {"Model": "iPhone"}))
    assert alice.get(f"/items/{item_id}").status_code == 200
    assert bob.get(f"/items/{item_id}").status_code == 404
    assert b"iPhone" not in bob.get("/browse/").data


def test_my_items_lists_only_own(app, alice, bob):
    report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti"})
    report(app, bob, "Found", BOTTLE, {"Brand": "Nalgene"})
    mine = alice.get("/my-items/").get_data(as_text=True)
    assert "Yeti" in mine and "Nalgene" not in mine


def test_only_owner_or_admin_can_delete(app, alice, bob):
    item_id = item_id_from(report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}))
    assert bob.post(f"/items/{item_id}/delete").status_code == 404
    assert alice.get(f"/items/{item_id}/delete").status_code == 405  # no delete via GET
    assert alice.post(f"/items/{item_id}/delete").status_code == 302
    assert alice.get(f"/items/{item_id}").status_code == 404


def test_admin_can_delete_anyones_item(app, alice, login):
    from lostlocker import db

    item_id = item_id_from(report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}))
    admin = login("admin@example.com", "Admin")
    with app.app_context():
        conn = db.get_db()
        conn.cursor().execute("UPDATE users SET is_admin = true WHERE email = 'admin@example.com'")
        conn.commit()
    assert admin.post(f"/items/{item_id}/delete").status_code == 302


def test_mark_returned_removes_from_locker(app, alice, bob):
    item_id = item_id_from(report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}))
    assert bob.post(f"/items/{item_id}/returned").status_code == 404
    assert alice.post(f"/items/{item_id}/returned").status_code == 302
    assert b"Yeti" not in bob.get("/browse/").data
    assert "Returned" in alice.get(f"/items/{item_id}").get_data(as_text=True)


def test_found_item_shows_claim_instructions_to_others(app, alice, bob):
    item_id = item_id_from(report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}))
    assert b"Is this yours?" in bob.get(f"/items/{item_id}").data
    assert b"Is this yours?" not in alice.get(f"/items/{item_id}").data


def test_notes_are_escaped(app, alice):
    item_id = item_id_from(
        report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}, notes="<script>alert(1)</script>")
    )
    html = alice.get(f"/items/{item_id}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_attribute_fixture_helper(app):
    assert attribute_id(app, "Brand", "Nike") == 105


# ------------------------------------------------------------------------------ photos


def test_photo_upload_is_stored_and_served(app, alice):
    response = report(
        app,
        alice,
        "Found",
        BOTTLE,
        {"Brand": "Yeti"},
        **{"image-upload": (png_bytes(), "photo.png")},
    )
    item_id = item_id_from(response)
    page = alice.get(f"/items/{item_id}").get_data(as_text=True)
    src = re.search(r'src="(/images/[^"]+)"', page).group(1)
    image = alice.get(src)
    assert image.status_code == 200
    assert image.mimetype == "image/jpeg"  # re-encoded, whatever was uploaded


def test_photo_is_optional(app, alice):
    assert report(app, alice, "Found", BOTTLE, {"Brand": "Yeti"}).status_code == 302


def test_non_image_upload_is_rejected_and_nothing_saved(app, alice):
    from io import BytesIO

    response = report(
        app,
        alice,
        "Found",
        BOTTLE,
        {"Brand": "Yeti"},
        **{"image-upload": (BytesIO(b"<?php echo 1; ?>"), "shell.jpg")},
    )
    assert response.status_code == 400
    assert b"valid photo" in response.data
    assert b"Yeti" not in alice.get("/my-items/").data  # no item row created


def test_unsupported_image_format_is_rejected(app, alice):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (5, 5)).save(buf, format="GIF")
    buf.seek(0)
    response = report(
        app, alice, "Found", BOTTLE, {"Brand": "Yeti"}, **{"image-upload": (buf, "x.gif")}
    )
    assert response.status_code == 400
    assert b"JPG, PNG or WebP" in response.data


def test_image_route_rejects_path_traversal(alice):
    assert alice.get("/images/..%2f..%2fetc%2fpasswd").status_code == 404
    assert alice.get("/images/notahexname.jpg").status_code == 404


def test_deleting_an_item_deletes_its_photo(app, alice):
    from pathlib import Path

    response = report(
        app,
        alice,
        "Found",
        BOTTLE,
        {"Brand": "Yeti"},
        **{"image-upload": (png_bytes(), "photo.png")},
    )
    folder = Path(app.config["UPLOAD_FOLDER"])
    assert len(list(folder.iterdir())) == 1
    alice.post(f"/items/{item_id_from(response)}/delete")
    assert list(folder.iterdir()) == []


def test_oversized_upload_is_rejected(app, alice):
    app.config["MAX_CONTENT_LENGTH"] = 1000
    response = report(
        app,
        alice,
        "Found",
        BOTTLE,
        {"Brand": "Yeti"},
        **{"image-upload": (png_bytes((300, 300)), "big.png")},
    )
    assert response.status_code == 413
