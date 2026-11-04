# Lost Locker

A lost-and-found site for students, built as a year-long project for the University of San Diego
student web portal. (Not affiliated with USD.)

- **Lost something?** Describe it. If something similar has already been turned in, you see it
  straight away. If not, the report is kept, and you get an email when a matching item is turned in.
- **Found something?** Add it to the locker with a photo. If it matches someone's lost report,
  they are emailed.
- **Browse** everything waiting to be claimed, with search, filters and paging.
- **My items** lists your own reports. You can mark them returned or delete them.

Lost reports are private to their owner. Found items are visible to logged-in users.

## Stack

Flask · PostgreSQL (psycopg2, connection pool) · Pillow · Flask-WTF (CSRF) · gunicorn.
No JavaScript is needed. The pages are server-rendered.

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
  items.py          report, browse, my items, item page, delete, photos
  api.py            JSON: item types and their allowed attributes
  matching.py       scoring and storing matches
  notifications.py  email
  uploads.py        photo validation and storage
  catalog.py        item types and attribute options
  templates/ static/
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
