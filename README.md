# Tabby

Tabby helps flatmates and trip groups log shared expenses and settle up with the fewest possible transfers. You sign up once, stay logged in, add your friends, put them in groups (a flat, a trip) and record who paid for what.

It is a single Python process (FastAPI + uvicorn) with a SQLite database, built for SDD Individual Assignment 1.

## Run locally

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:8000/>. The interactive API docs are at <http://localhost:8000/docs>.

No setup step is needed: on first start the app creates its data directory, the SQLite file and any missing tables.

## Configuration

Everything is configured through environment variables. None are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the HTTP server listens on. The server always binds `0.0.0.0`. |
| `DATA_DIR` | `./data` (next to `app.py`) | Directory that holds the SQLite file. The container sets it to `/data`. |
| `SESSION_DAYS` | `30` | How long a login is remembered (lifetime of the session cookie and its database row). |

Example: `PORT=9000 DATA_DIR=/tmp/tabby python app.py`

## Database

- SQLite file: `$DATA_DIR/tabby.db` (locally `./data/tabby.db`, in the container `/data/tabby.db`).
- Schema: one `schema.sql` per domain ([accounts](tabby/accounts/schema.sql), [ledger](tabby/ledger/schema.sql)), applied on every boot. They only use `CREATE ... IF NOT EXISTS`, so existing tables and rows are never dropped or changed.
- The `.db` file is never committed; it is created at runtime.

## Run with Docker

The [Dockerfile](Dockerfile) is the course template with its four TODOs filled in.

```bash
docker build -t tabby .
docker run -p 8000:8000 -v tabby-data:/data tabby
```

The database is written to `/data/tabby.db` inside the named volume `tabby-data`, so it survives `docker rm`. To use another port: `docker run -e PORT=9000 -p 9000:9000 -v tabby-data:/data tabby`.

## API overview

All endpoints are under `/api` and documented interactively at `/docs`. Everything except sign-up and login needs the `tabby_session` cookie that those two set.

| Domain | Endpoints |
|---|---|
| Accounts | `POST /api/signup`, `POST /api/login`, `POST /api/logout`, `GET /api/me`, `GET/POST /api/friends` |
| Ledger (Domain A) | `GET/POST /api/groups`, `GET /api/groups/{id}`, `POST /api/groups/{id}/members`, `DELETE /api/groups/{id}/members/{user_id}`, `GET/POST /api/groups/{id}/expenses`, `DELETE /api/groups/{id}/expenses/{expense_id}` |

Money is always sent and stored as integer cents (`amount_cents`). An expense's `split_type` is `equal`, `shares` (each participant's `value` is a weight) or `exact` (each `value` is cents owed, and they must add up to the amount).

## Project structure

```
app.py                 entry point: python app.py
tabby/
  config.py            settings from environment variables
  db.py                SQLite connection + first-boot schema creation
  errors.py            domain errors -> HTTP status codes
  main.py              builds the FastAPI app and registers each domain's routes
  accounts/            users, login sessions, friends
  ledger/              Domain A: groups, members, expenses, split rules
```

Each domain has `routes.py` (HTTP), `service.py` (business rules), `repository.py` (SQL), `schema.sql` (its tables) and `interface.py`, the only module other domains may import (see ADR-2).

## Tests and coverage

_To be added._

## Container contract check (§7)

Output of `./container/run.sh .` (first pass, 2026-10-09, after the ledger domain; re-run before submission):

```
=== SDD Assignment 1 contract check ===
Repository: /Users/sergehagopian/Desktop/Software Devops Assignment 1

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 52 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: tabby.db 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: expense_groups=0 expense_shares=0 expenses=0 friendships=0 group_members=0 sessions=0 users=0 

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

## Project docs

- [ADR.md](ADR.md): architecture decision log
- [AI_USAGE.md](AI_USAGE.md): AI usage log
