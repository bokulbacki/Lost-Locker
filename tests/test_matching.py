from __future__ import annotations

import pytest

from lostlocker import db
from lostlocker.matching import find_matches, is_vague, normalize_title, title_score

from .conftest import item_id_from, report

CLOTHING, BOTTLE, DEVICE, BAG, BOOK = 1, 2, 3, 4, 5


def match_rows(app):
    with app.app_context():
        cur = db.get_db().cursor()
        cur.execute("SELECT lost_item_id, found_item_id, score, notified_at FROM matches")
        return cur.fetchall()


def test_title_scoring():
    assert normalize_title("  The  Great Gatsby! ") == "the great gatsby"
    assert title_score("The Great Gatsby", "the great gatsby") == 3.0
    assert title_score("Gatsby", "The Great Gatsby") == 2.0
    assert title_score("Dune", "Emma") == 0.0
    assert title_score("", "Emma") == 0.0
    assert title_score(None, None) == 0.0


def test_vague_values_never_count():
    assert is_vague("Other") and is_vague("Other/Unknown")
    assert not is_vague("Nike")


def test_found_item_matches_earlier_lost_report_and_emails_owner(app, alice, bob, outbox):
    lost_id = item_id_from(report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti", "Color": "Red"}))
    assert outbox == []

    report(app, bob, "Found", BOTTLE, {"Brand": "Yeti", "Color": "Red", "Location": "Tram"})

    rows = match_rows(app)
    assert len(rows) == 1 and rows[0]["lost_item_id"] == lost_id
    assert rows[0]["notified_at"] is not None
    assert len(outbox) == 1 and outbox[0]["to"] == "alice@example.com"
    assert f"/items/{lost_id}" in outbox[0]["body"]

    page = alice.get(f"/items/{lost_id}").get_data(as_text=True)
    assert "Possible matches" in page and "Yeti" in page


def test_lost_report_matches_existing_found_items_immediately(app, alice, bob, outbox):
    report(app, bob, "Found", DEVICE, {"Brand": "Apple", "Model": "iPhone"})
    response = report(app, alice, "Lost", DEVICE, {"Brand": "Apple", "Model": "iPhone"})
    assert len(match_rows(app)) == 1
    flashed = alice.get(response.headers["Location"]).get_data(as_text=True)
    assert "1 possible match" in flashed
    assert outbox == []  # the person looking already sees it on screen


def test_weak_similarity_is_not_a_match(app, alice, bob, outbox):
    report(app, alice, "Lost", BOTTLE, {"Color": "Red", "Location": "Tram"})
    report(app, bob, "Found", BOTTLE, {"Color": "Red", "Location": "Tram"})  # 1.25 < 1.5
    assert match_rows(app) == []
    assert outbox == []


def test_different_item_types_never_match(app, alice, bob):
    report(app, alice, "Lost", BAG, {"Brand": "Nike", "Color": "Black"})
    report(app, bob, "Found", CLOTHING, {"Brand": "Nike", "Color": "Black"})
    assert match_rows(app) == []


def test_vague_values_do_not_create_matches(app, alice, bob):
    report(app, alice, "Lost", CLOTHING, {"Brand": "Other/Unknown", "ClothingType": "Other"})
    report(app, bob, "Found", CLOTHING, {"Brand": "Other/Unknown", "ClothingType": "Other"})
    assert match_rows(app) == []


def test_books_match_by_title(app, alice, bob, outbox):
    report(app, alice, "Lost", BOOK, {}, book_title="The Great Gatsby")
    report(app, bob, "Found", BOOK, {}, book_title="great gatsby")
    assert len(match_rows(app)) == 1
    assert len(outbox) == 1


def test_ranking_prefers_better_matches(app, alice, bob):
    lost = item_id_from(report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti", "Color": "Red"}))
    ok = item_id_from(report(app, bob, "Found", BOTTLE, {"Brand": "Yeti"}))
    best = item_id_from(report(app, bob, "Found", BOTTLE, {"Brand": "Yeti", "Color": "Red"}))
    with app.app_context():
        ranked = find_matches(db.get_db().cursor(), lost, 1.5)
    assert [i for i, _ in ranked] == [best, ok]
    assert ranked[0][1] > ranked[1][1]


def test_returned_items_are_not_matched(app, alice, bob, outbox):
    found = item_id_from(report(app, bob, "Found", BOTTLE, {"Brand": "Yeti"}))
    bob.post(f"/items/{found}/returned")
    report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti"})
    assert match_rows(app) == []


def test_no_duplicate_matches_or_emails(app, alice, bob, outbox):
    report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti"})
    found = item_id_from(report(app, bob, "Found", BOTTLE, {"Brand": "Yeti"}))
    from lostlocker.matching import record_matches

    with app.app_context():
        conn = db.get_db()
        assert record_matches(conn.cursor(), found, 1.5) == []  # already recorded
    assert len(match_rows(app)) == 1 and len(outbox) == 1


def test_email_failure_does_not_break_reporting(app, alice, bob, monkeypatch):
    monkeypatch.setattr("lostlocker.notifications.send_email", lambda *a: False)
    report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti"})
    assert report(app, bob, "Found", BOTTLE, {"Brand": "Yeti"}).status_code == 302
    assert match_rows(app)[0]["notified_at"] is None  # stays pending


def test_send_email_logs_when_unconfigured(caplog):
    from lostlocker.notifications import send_email

    cfg = {"MAIL_SERVER": ""}
    with caplog.at_level("INFO"):
        assert send_email(cfg, "a@example.com", "Hi", "Body") is False
    assert "a@example.com" in caplog.text


def test_send_email_smtp(monkeypatch):
    from lostlocker import notifications

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            calls.append("tls")

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    cfg = {
        "MAIL_SERVER": "smtp.example.com",
        "MAIL_PORT": 587,
        "MAIL_USE_TLS": True,
        "MAIL_USERNAME": "u",
        "MAIL_PASSWORD": "p",
        "MAIL_FROM": "from@example.com",
    }
    assert notifications.send_email(cfg, "to@example.com", "Subj", "Body") is True
    assert calls == [
        ("connect", "smtp.example.com", 587),
        "tls",
        ("login", "u"),
        ("send", "to@example.com", "Subj"),
    ]


def test_send_email_swallows_network_errors(monkeypatch):
    from lostlocker import notifications

    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(notifications.smtplib, "SMTP", boom)
    cfg = {
        "MAIL_SERVER": "x",
        "MAIL_PORT": 25,
        "MAIL_USE_TLS": False,
        "MAIL_USERNAME": "",
        "MAIL_PASSWORD": "",
        "MAIL_FROM": "f@example.com",
    }
    assert notifications.send_email(cfg, "to@example.com", "S", "B") is False


@pytest.mark.parametrize("threshold, expected", [(1.5, True), (1.6, False)])
def test_threshold_boundary(app, alice, bob, threshold, expected):
    # A shared brand scores exactly 1.5, so it matches at 1.5 but not at 1.6.
    lost = item_id_from(report(app, alice, "Lost", BOTTLE, {"Brand": "Yeti"}))
    report(app, bob, "Found", BOTTLE, {"Brand": "Yeti"})
    with app.app_context():
        cur = db.get_db().cursor()
        assert bool(find_matches(cur, lost, threshold)) is expected
