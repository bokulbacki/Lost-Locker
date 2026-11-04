# Lost Locker

A lost-and-found site for students, built as a year-long project for the University of San Diego
student web portal. (Not affiliated with USD.)

- **Lost something?** Pick what it is, then tap what you remember: brand, colour, where. Every
  detail is optional except one. If something similar has already been turned in, you see it
  straight away. If not, the report is kept, and you get an email when a match is turned in.
- **Found something?** Add a photo if you like, say where the item is now (with you, at the lost &
  found desk, or where you found it), and optionally write a question only the owner could answer.
- **Claims.** An owner who spots their item answers the finder's question. The finder approves or
  declines. Contact details are shared only after approval.
- **Home** is a landing page for visitors and, once you sign in, a short "needs your attention" list
  (possible matches, claims to review) plus a step-by-step progress tracker on each report.
- **Browse** everything waiting to be claimed, with search, filters and paging.
- **My items** groups your reports by status. You can mark them returned or delete them.

Lost reports are private to their owner. Found items are visible to logged-in users.

## Accessibility

The goal is that anyone can report an item in under a minute, on a phone, with one hand.

- Big tap targets (44px minimum). Choices are chips and colour swatches instead of long dropdowns,
  and they are real radio buttons, so they work with keyboards and screen readers.
- A **Display** menu in every page header: light / dark / system theme, high contrast, and three
  text sizes. Choices are remembered in the browser.
- Skip link, landmarks, one `h1` per page, visible focus, and form errors in a summary that receives
  focus and links to each field. Colour is never the only signal. Reduced-motion is respected.
- Works without JavaScript apart from the Display menu, photo preview and show-password toggle.
- On phones, the main navigation moves to a bottom bar. Layouts reflow down to 320px wide, even at
  the largest text size.
- **QR codes at drop-off spots.** `/foundItem/?loc=Copley%20Library` opens the "I found something"
  form with that location already chosen. Print one per building.

Checked with axe-core (WCAG 2.2 AA and best-practice rules) in Chrome across light, dark, high
contrast and large text, at desktop and 375px widths: no violations. That is automated testing only.
It has not been tried with a screen reader or by disabled users, so please do that before relying on it.

## Stack

Flask · PostgreSQL (psycopg2, connection pool) · Pillow · Flask-WTF (CSRF) · gunicorn.
Pages are server-rendered. A small amount of plain JavaScript (no framework) handles the Display menu and photo preview.

## Run it locally

You need Python 3.12+ and a PostgreSQL database.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit it: set SECRET_KEY and DATABASE_URL
flask --app lostlocker migrate        # creates the tables and loads the reference data
flask --app lostlocker run --debug    # http://localhost:5000
```

Register an account in the browser. To make yourself an admin (admins can delete anyone's report):

```bash
flask --app lostlocker make-admin you@example.com
```

### With Docker

```bash
cp .env.example .env     # set SECRET_KEY and DB_PASSWORD
docker compose up --build
```

The site is on http://localhost:8000. Compose runs migrations before starting the server.

## Configuration

All settings come from environment variables or a `.env` file. See [`.env.example`](.env.example).

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | **Required** unless running with `--debug`. Signs session cookies. |
| `DATABASE_URL` | Postgres connection URL. Or use `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` and `DB_SSLMODE`. |
| `SESSION_COOKIE_SECURE` | Set to `true` when served over HTTPS. |
| `UPLOAD_FOLDER` | Where photos are stored (default `instance/uploads`). |
| `ALLOWED_EMAIL_DOMAIN` | Optional, e.g. `sandiego.edu`, to restrict registration. |
| `MAIL_SERVER` and related | SMTP settings for match emails. If `MAIL_SERVER` is empty, emails are logged instead of sent. |
| `BASE_URL` | Used for links in emails. |
| `CLAIM_INSTRUCTIONS` | Text shown on a found item telling the owner how to claim it. |
| `MATCH_MIN_SCORE` | How similar a lost and found report must be to count as a match (default 1.5). |

## How matching works

A lost report and a found report are compared only when they are the same item type. Each shared
detail adds to a score: clothing type or device model 2.0, brand 1.5, colour 1.0, size or stickers
or cap type 0.5, location 0.25. Books are compared by title. "Other" and "Other/Unknown" never
count. Pairs at or above `MATCH_MIN_SCORE` are saved as matches (best first) and the owner of the
lost report is emailed. The weights are in [`lostlocker/matching.py`](lostlocker/matching.py).

## Project layout

```
lostlocker/
  __init__.py       app factory, security headers, error pages, CLI commands
  config.py         settings from the environment
  db.py             connection pool and migration runner
  migrations/       numbered .sql files, applied in order by `flask migrate`
  auth.py           register / login / logout
  items.py          home/dashboard, browse, my items, item page, delete, photos
  report.py         the two-step lost / found form
  claims.py         claim, approve, decline
  api.py            JSON: item types and their allowed attributes
  matching.py       scoring and storing matches
  notifications.py  email
  uploads.py        photo validation and storage
  catalog.py        item types and attribute options
  templates/ static/   (css/app.css is the whole design system; js/ is the Display menu etc.)
tests/              pytest suite
```

Schema changes go in a new numbered file in `lostlocker/migrations/`. Don't edit applied ones.

## Tests and linting

```bash
pip install -r requirements-dev.txt
pytest              # starts a temporary embedded PostgreSQL; or set TEST_DATABASE_URL
ruff check . && ruff format --check .
```

CI runs the same checks on every pull request.

## Security notes

- Passwords are hashed. Sessions use HttpOnly, SameSite=Lax cookies. Every form has a CSRF token.
- All SQL is parameterized.
- Uploaded photos are decoded, size-limited, stripped of metadata and re-saved as JPEG under random
  names. They are served only to logged-in users.
- Pages are served with a strict Content-Security-Policy. There is no inline script and there are no
  third-party hosts.

## Upgrading from the original version

The original app used a different schema and had no accounts, and its database credentials were
committed to the repository. If you used it:

1. **Rotate the old database password.** It is in the git history.
2. Existing reports are not migrated. The old data had no owners, and the schema changed. Start from
   the new schema with `flask migrate`.
3. Old uploaded photos were removed from the repository. They are not linked to any new reports.
