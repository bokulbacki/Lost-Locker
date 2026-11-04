"""Tests for the accessible redesign: landing/dashboard, claims, report details, a11y structure."""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from markupsafe import escape

from lostlocker import catalog
from lostlocker.items import progress_steps
from lostlocker.report import parse_date

from .conftest import item_id_from, png_bytes, report

BOTTLE, DEVICE = 2, 3


def _found_bottle(app, finder, **extra):
    resp = report(app, finder, "Found", BOTTLE, {"Brand": "Hydro Flask"}, **extra)
    assert resp.status_code == 302
    return item_id_from(resp)


def _claim(client, item_id, answer="It has a dent on the bottom"):
    return client.post(f"/items/{item_id}/claim", data={"answer": answer})


def _claim_id(client, item_id):
    html = client.get(f"/items/{item_id}").get_data(as_text=True)
    return int(re.search(r"/claims/(\d+)/approve", html).group(1))


# ---------------------------------------------------------------- landing + dashboard


def test_landing_is_public(client):
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Lost Locker" in html
    assert 'href="/lostitem/"' in html and 'href="/foundItem/"' in html


def test_landing_has_skip_link_and_single_h1(client):
    html = client.get("/").get_data(as_text=True)
    assert 'class="skip-link"' in html and 'href="#main"' in html
    assert html.count("<h1") == 1
    assert '<html lang="en">' in html


def test_dashboard_shows_possible_match(app, alice, bob):
    report(app, alice, "Lost", BOTTLE, {"Brand": "Hydro Flask"})
    _found_bottle(app, bob)
    html = alice.get("/").get_data(as_text=True)
    assert "possible match" in html


def test_dashboard_shows_pending_claim_to_finder(app, alice, bob):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    html = alice.get("/").get_data(as_text=True)
    assert "thinks" in html and "Review" in html


def test_dashboard_for_new_user_has_no_attention_list(alice):
    resp = alice.get("/")
    assert resp.status_code == 200
    assert "possible match" not in resp.get_data(as_text=True)


# ---------------------------------------------------------------- claims


def test_claim_flow_approve_reveals_finder_contact(app, alice, bob, outbox):
    item_id = _found_bottle(app, alice, verify_question="What sticker is on it?")
    # before claiming, the finder's email is not shown
    assert "alice@example.com" not in bob.get(f"/items/{item_id}").get_data(as_text=True)
    assert "What sticker is on it?" in bob.get(f"/items/{item_id}").get_data(as_text=True)

    assert _claim(bob, item_id).status_code == 302
    assert any("thinks the item" in m["subject"] or "theirs" in m["subject"] for m in outbox)
    pending = bob.get(f"/items/{item_id}").get_data(as_text=True)
    assert "alice@example.com" not in pending

    claim_id = _claim_id(alice, item_id)
    assert alice.post(f"/claims/{claim_id}/approve").status_code == 302
    assert any("approved" in m["subject"] for m in outbox)

    approved = bob.get(f"/items/{item_id}").get_data(as_text=True)
    assert "alice@example.com" in approved


def test_claim_decline_keeps_contact_hidden(app, alice, bob, outbox):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    claim_id = _claim_id(alice, item_id)
    assert alice.post(f"/claims/{claim_id}/decline").status_code == 302
    assert any("approved" in m["subject"] and "wasn" in m["subject"] for m in outbox)
    html = bob.get(f"/items/{item_id}").get_data(as_text=True)
    assert "alice@example.com" not in html
    assert "Claim not approved" in html


def test_duplicate_claim_is_rejected(app, alice, bob):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    resp = _claim(bob, item_id)
    assert resp.status_code == 302
    html = bob.get(f"/items/{item_id}").get_data(as_text=True)
    assert "already sent a claim" in html


def test_cannot_claim_own_item(app, alice):
    item_id = _found_bottle(app, alice)
    _claim(alice, item_id)
    assert "nothing to claim" in alice.get(f"/items/{item_id}").get_data(as_text=True)


def test_claim_requires_answer(app, alice, bob):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id, answer="   ")
    assert "Please answer the question" in bob.get(f"/items/{item_id}").get_data(as_text=True)


def test_cannot_claim_lost_report(app, alice, bob):
    resp = report(app, alice, "Lost", BOTTLE, {"Brand": "Hydro Flask"})
    assert _claim(bob, item_id_from(resp)).status_code == 404


def test_only_finder_can_decide(app, alice, bob, login):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    claim_id = _claim_id(alice, item_id)
    carol = login("carol@example.com", "Carol")
    assert carol.post(f"/claims/{claim_id}/approve").status_code == 404
    assert bob.post(f"/claims/{claim_id}/approve").status_code == 404
    assert alice.post(f"/claims/{claim_id}/bogus").status_code == 404
    assert alice.post("/claims/9999/approve").status_code == 404


def test_decided_claim_cannot_be_redecided(app, alice, bob):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    claim_id = _claim_id(alice, item_id)
    alice.post(f"/claims/{claim_id}/decline")
    alice.post(f"/claims/{claim_id}/approve")
    assert "Claim not approved" in bob.get(f"/items/{item_id}").get_data(as_text=True)


def test_returned_item_cannot_be_claimed(app, alice, bob):
    item_id = _found_bottle(app, alice)
    alice.post(f"/items/{item_id}/returned")
    _claim(bob, item_id)
    assert "already been returned" in bob.get(f"/items/{item_id}").get_data(as_text=True)


def test_mark_returned_declines_pending_claims(app, alice, bob):
    item_id = _found_bottle(app, alice)
    _claim(bob, item_id)
    alice.post(f"/items/{item_id}/returned")
    assert "Claim not approved" in bob.get(f"/items/{item_id}").get_data(as_text=True)


def test_claim_requires_login(app, alice, client):
    item_id = _found_bottle(app, alice)
    resp = client.post(f"/items/{item_id}/claim", data={"answer": "x"})
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


# ---------------------------------------------------------------- report form


def test_report_form_prefills_location_from_query(alice):
    html = alice.get("/foundItem/?type=2&loc=Copley%20Library").get_data(as_text=True)
    option = re.search(r'<option[^>]*value="\d+"[^>]*selected[^>]*>\s*Copley Library', html)
    assert option, "Copley Library should be pre-selected"


def test_report_form_ignores_unknown_location(alice):
    assert alice.get("/foundItem/?type=2&loc=Narnia").status_code == 200


def test_report_errors_are_field_linked(app, alice):
    resp = alice.post(
        "/lostitem/",
        data={"itemtype_id": str(BOTTLE), "attr:Brand": "99999"},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert resp.status_code == 400
    assert 'href="#attr-brand"' in html
    assert "pick one of the listed options" in html


def test_report_rejects_future_date(app, alice):
    future = (date.today() + timedelta(days=2)).isoformat()
    resp = report(app, alice, "Lost", BOTTLE, {"Brand": "Hydro Flask"}, happened_on=future)
    assert resp.status_code == 400
    assert "be in the future" in resp.get_data(as_text=True)


def test_report_rejects_bad_held_at_for_found(app, alice):
    resp = report(app, alice, "Found", BOTTLE, {"Brand": "Hydro Flask"}, held_at="in my shoe")
    assert resp.status_code == 400


def test_report_requires_a_detail(app, alice):
    resp = alice.post(
        "/lostitem/", data={"itemtype_id": str(BOTTLE)}, content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "at least one detail" in resp.get_data(as_text=True)


def test_report_stores_date_and_held_at(app, alice):
    when = (date.today() - timedelta(days=3)).isoformat()
    item_id = _found_bottle(
        app, alice, happened_on=when, held_at=catalog.HELD_OPTIONS[1], notes="Near the stairs"
    )
    html = alice.get(f"/items/{item_id}").get_data(as_text=True)
    assert escape(catalog.HELD_OPTIONS[1]) in html
    assert "Near the stairs" in html


def test_photo_upload_still_works(app, alice):
    resp = report(
        app,
        alice,
        "Found",
        BOTTLE,
        {"Brand": "Hydro Flask"},
        **{"image-upload": (png_bytes(), "photo.png")},
    )
    item_id = item_id_from(resp)
    html = alice.get(f"/items/{item_id}").get_data(as_text=True)
    src = re.search(r'src="(/images/[^"]+)"', html).group(1)
    assert alice.get(src).status_code == 200


# ---------------------------------------------------------------- helpers


@pytest.mark.parametrize(
    ("raw", "ok"),
    [
        ("", True),
        (date.today().isoformat(), True),
        ((date.today() - timedelta(days=5)).isoformat(), True),
        ((date.today() + timedelta(days=1)).isoformat(), False),
        ((date.today() - timedelta(days=400)).isoformat(), False),
        ("not-a-date", False),
        ("2024-13-40", False),
    ],
)
def test_parse_date(raw, ok):
    value, error = parse_date(raw)
    assert (error is None) is ok
    assert (value is not None) is ok


def test_widget_for():
    assert catalog.widget_for("Color", 12) == "swatch"
    assert catalog.widget_for("Brand", 5) == "chips"
    assert catalog.widget_for("Brand", 20) == "select"
    assert catalog.widget_for("Location", 3) == "select"


def test_slug():
    assert catalog.slug("Cap Type") == "cap-type"
    assert catalog.slug("Backpack/Bag/Purse") == "backpack-bag-purse"


def test_describe():
    item = {
        "book_title": None,
        "itemtype": "Bottle",
        "details": [
            {"group": "Color", "value": "Blue"},
            {"group": "Brand", "value": "Hydro Flask"},
            {"group": "Model", "value": "Other/Unknown"},
        ],
    }
    assert catalog.describe(item) == "Blue Hydro Flask Bottle"
    assert catalog.describe({"book_title": "Dune", "itemtype": "Book", "details": []}) == "“Dune”"


def _states(item, **kw):
    return [s["state"] for s in progress_steps(item, **kw)]


def test_progress_steps_lost():
    base = {"reported_as": "Lost", "status": "Lost"}
    kw = {"has_claims": False, "approved": False}
    assert _states(base, has_matches=False, **kw) == ["done", "current", "todo", "todo"]
    assert _states(base, has_matches=True, **kw) == ["done", "done", "current", "todo"]
    returned = {"reported_as": "Lost", "status": "Returned"}
    assert _states(returned, has_matches=True, **kw) == ["done"] * 4


def test_progress_steps_found():
    base = {"reported_as": "Found", "status": "Found"}
    none = {"has_matches": False}
    assert _states(base, has_claims=False, approved=False, **none) == [
        "current",
        "todo",
        "todo",
        "todo",
    ]
    assert _states(base, has_claims=True, approved=False, **none)[:2] == ["done", "current"]
    assert _states(base, has_claims=True, approved=True, **none)[:3] == [
        "done",
        "done",
        "current",
    ]
    returned = {"reported_as": "Found", "status": "Returned"}
    assert _states(returned, has_claims=True, approved=True, **none) == ["done"] * 4


# ---------------------------------------------------------------- structural a11y


@pytest.mark.parametrize("path", ["/", "/browse/", "/my-items/", "/lostitem/", "/foundItem/"])
def test_pages_have_landmarks_and_title(alice, path):
    html = alice.get(path).get_data(as_text=True)
    assert "<main" in html and 'id="main"' in html
    assert re.search(r"<title>[^<]+</title>", html)
    assert html.count("<h1") == 1


def test_images_have_alt_text(app, alice):
    item_id = _found_bottle(app, alice)
    for path in ("/browse/", f"/items/{item_id}", "/my-items/"):
        for tag in re.findall(r"<img\b[^>]*>", alice.get(path).get_data(as_text=True)):
            assert "alt=" in tag
