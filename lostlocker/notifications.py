"""Emailing people when a report of theirs has a possible match."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def send_email(config, to: str, subject: str, body: str) -> bool:
    """Send via SMTP, or just log the message when MAIL_SERVER isn't configured."""
    if not config["MAIL_SERVER"]:
        log.info("Email not sent (MAIL_SERVER unset). To: %s | %s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = config["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10) as smtp:
            if config["MAIL_USE_TLS"]:
                smtp.starttls()
            if config["MAIL_USERNAME"]:
                smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send email to %s", to)
        return False
    return True


def notify_matches(config, conn, match_ids: list[int]) -> int:
    """Email the owner of the lost report for each new match. Returns how many were sent."""
    if not match_ids:
        return 0
    cur = conn.cursor()
    cur.execute(
        "SELECT m.match_id, m.lost_item_id, u.email, u.name, it.itemtype"
        " FROM matches m"
        " JOIN item l ON l.item_id = m.lost_item_id"
        " JOIN itemtype it ON it.itemtype_id = l.itemtype_id"
        " JOIN users u ON u.user_id = l.submitted_by_user"
        " WHERE m.match_id = ANY(%s) AND m.notified_at IS NULL AND l.status = 'Lost'",
        (match_ids,),
    )
    sent = 0
    for row in cur.fetchall():
        link = f"{config['BASE_URL']}/items/{row['lost_item_id']}"
        body = (
            f"Hi {row['name']},\n\n"
            f"Someone turned in an item that might be your lost {row['itemtype'].lower()}.\n"
            f"Take a look and see if it's yours:\n{link}\n\n"
            "Lost Locker"
        )
        if send_email(config, row["email"], "A possible match for your lost item", body):
            cur.execute(
                "UPDATE matches SET notified_at = now() WHERE match_id = %s", (row["match_id"],)
            )
            sent += 1
    conn.commit()
    return sent
