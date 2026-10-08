# Tabby

Tabby helps flatmates and trip groups log shared expenses and settle up with the fewest possible transfers.

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

Example: `PORT=9000 DATA_DIR=/tmp/tabby python app.py`

## Database

- SQLite file: `$DATA_DIR/tabby.db` (locally `./data/tabby.db`, in the container `/data/tabby.db`).
- Schema: [`tabby/schema.sql`](tabby/schema.sql), applied on every boot. It only uses `CREATE ... IF NOT EXISTS`, so existing tables and rows are never dropped or changed.
- The `.db` file is never committed; it is created at runtime.

## Run with Docker

_To be added with the Dockerfile._

## Tests and coverage

_To be added._

## Container contract check (§7)

_`run.sh` output to be added._

## Project docs

- [ADR.md](ADR.md): architecture decision log
- [AI_USAGE.md](AI_USAGE.md): AI usage log
