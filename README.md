# Tabby

Tabby helps flatmates and trip groups log shared expenses and settle up with the fewest possible transfers. You sign up once, add your friends, put them in groups (a flat, a trip) and record who paid for what.

It started as the single-process app of SDD Individual Assignment 1 and was split along its domain seam for Assignment 2 (ADR-6): two Python services (FastAPI + uvicorn), each with its own SQL Server database, and a static UI that calls both.

| Part | Folder | Owns | Database |
|---|---|---|---|
| `ledger` service | [services/ledger](services/ledger) | accounts (users, sessions, friends) and Domain A (groups, members, expenses, categories) | `ledger` |
| `settlement` service | [services/settlement](services/settlement) | Domain B (payments; computes balances and the settle-up plan) | `settlement` |
| UI | [ui](ui) | static HTML/JS/CSS; [config.js](ui/config.js) holds the two service URLs | none |

**The seam:** settlement calls `GET {LEDGER_URL}/api/groups/{id}/ledger` on the ledger service, forwarding the user's bearer token ([ledger_client.py](services/settlement/tabby/ledger_client.py)). The ledger answers with the members, every expense's per-member shares and who the caller is; settlement adds its own payments and computes the balances. If ledger is down, settlement answers `503` with a clear message and stays healthy; the UI keeps showing expenses and says balances are unavailable.

Live URL: *added after the first deployment.*

## Run the whole system locally

Requires Docker (on Apple Silicon, enable *Use Rosetta for x86_64/amd64 emulation* in Docker Desktop: SQL Server has no arm64 image).

```bash
cp .env.example .env          # local passwords; change them if you like
docker compose up --build
```

Open <http://localhost:8080/>, sign up, and add a friend by username (sign up a second account in a private window to try it alone). The first start takes about a minute: SQL Server must be healthy, then `db-init` creates the two databases and logins ([db/init.sql](db/init.sql)), then each service applies its migrations and starts.

| Container | URL | Notes |
|---|---|---|
| `ui` (nginx:alpine, folder mounted) | <http://localhost:8080> | static files only |
| `ledger` | <http://localhost:8001/docs> | API docs |
| `settlement` | <http://localhost:8002/docs> | API docs |
| `sqlserver` | `localhost:1433` | one server, two databases |

Try the partial failure: `docker compose stop settlement` (the group page shows expenses and "Balances and settle-up are unavailable right now") or `docker compose stop ledger` (settlement answers 503 and its `/health` stays 200). `docker compose start <service>` brings it back. `docker compose down -v` deletes all local data.

## Run one service without Docker

SQL Server must be running (`docker compose up -d sqlserver db-init`). Then, for example for ledger:

```bash
cd services/ledger
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
set -a && source ../../.env && set +a
DATABASE_URL="mssql://ledger_user:${LEDGER_DB_PASSWORD}@localhost:1433/ledger" PORT=8001 python app.py
```

For settlement use `settlement_user`, `SETTLEMENT_DB_PASSWORD`, database `settlement`, `PORT=8002` and `LEDGER_URL=http://localhost:8001`.

## Configuration

Everything is configured through environment variables ([system.yaml](system.yaml) lists them per service).

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | both | none (secret, required) | `mssql://user:password@host:1433/database` of the service's own database |
| `PORT` | both | `8000` | Port the HTTP server listens on (always `0.0.0.0`) |
| `CORS_ORIGINS` | both | empty (no cross-origin calls) | The UI's origin, e.g. `http://localhost:8080`; comma-separated |
| `GIT_SHA` | both | `dev` | Commit the image was built from (Docker build arg), reported by `/health` |
| `SESSION_DAYS` | ledger | `30` | How long a session token is valid |
| `LEDGER_URL` | settlement | `http://localhost:8001` | Base URL of the ledger service (compose: `http://ledger:8000`) |
| `LEDGER_TIMEOUT_S` | settlement | `5` | Timeout of every call to the ledger service |

## Database and migrations

- Each service has its own database and login: `ledger_user` can only use `ledger`, `settlement_user` only `settlement`. Ids that cross the seam (`payments.group_id`, user ids) have no foreign key (ADR-7).
- The schema is defined by numbered files in `services/<name>/migrations/` (`001_init.sql`, ...). On startup, before accepting requests, each service applies the files not yet recorded in its `schema_migrations` table, each in one transaction, and logs `applying migration ...`. A second start applies nothing. Applied files are never edited; changes go in a new file.
- Seed data: the starter categories ([seed_categories.csv](services/ledger/tabby/ledger/seed_categories.csv)) are inserted only when the `categories` table is empty.

## Health and logs

`GET /health` on each service writes and reads a row in its own database and returns `200 {"status": "ok", "db": "ok", "version": "<git sha>"}`, or `503` when it cannot. It does not depend on the other service. Every request is logged to stdout as one line: `GET /api/groups/1/settlement 200 24ms`.

## Tests and coverage

Each service has unit tests (split rounding, settle-up algorithm, password hashing, services and HTTP routes) that run against a real SQL Server database, created fresh for each run from the migrations. The cross-seam integration test runs the real settlement app with the ledger replaced by an HTTP stub that is checked against ledger's `openapi.json` ([test_api.py](services/settlement/tests/test_api.py)); the same flow also runs against the real compose stack ([tests/e2e/cross_seam.py](tests/e2e/cross_seam.py)). See ADR-9.

```bash
docker compose up -d sqlserver
set -a && source .env && set +a
cd services/ledger && TEST_DATABASE_URL="mssql://sa:${SA_PASSWORD}@localhost:1433/ledger_test" pytest --cov=tabby
cd services/settlement && TEST_DATABASE_URL="mssql://sa:${SA_PASSWORD}@localhost:1433/settlement_test" pytest --cov=tabby
```

Result on 2026-11-21: ledger **371 passed, 98%** coverage; settlement **91 passed, 96%**.

End to end, with the stack running: `python3 tests/e2e/cross_seam.py flow`, then `docker compose stop ledger` and `python3 tests/e2e/cross_seam.py ledger-down`.

## CI/CD

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push and pull request: `ruff` and `pytest` per service against a throwaway SQL Server container with a random password (fails under 70% coverage), validation of both OpenAPI documents, a Docker build of each image, and the cross-seam test on the compose stack. It never connects to Azure.

## Deployment to Azure

Everything runs in my own Azure for Students subscription, in one resource group. It is created once by a script and after that deployed only by GitHub Actions, never by hand in the portal. Names come from [infra/config.sh](infra/config.sh) and all start with `shagopian-ieu2024`.

| Resource | Name | Plan |
|---|---|---|
| Resource group | `rg-shagopian-ieu2024` | |
| Managed identity | `shagopian-ieu2024-github` | what the pipeline signs in as (OpenID Connect); Contributor on the resource group only |
| Container Apps environment | `shagopian-ieu2024-env` | Consumption, with the Log Analytics workspace Azure creates for it |
| Container Apps | `shagopian-ieu2024-ledger`, `shagopian-ieu2024-settlement` | 0.25 vCPU / 0.5 GiB, 0 to 1 replica |
| Azure SQL server | `shagopian-ieu2024-sql` | logins `ledger_user`, `settlement_user` |
| Databases | `shagopian-ieu2024-ledger-db`, `shagopian-ieu2024-settlement-db` | serverless GP Gen5, 0.5-1 vCore, Azure SQL free offer (auto-pause 60 min, 32 GB), LRS backups |
| UI | storage account `shagopianieu2024ui1` (static website) | Standard LRS, pay per GB and request |
| Images | `ghcr.io/sergegod/tabby-ledger:<sha>`, `ghcr.io/sergegod/tabby-settlement:<sha>` | public |

### Initial setup (once)

1. Sign in with `az login` (Azure for Students subscription) and `gh auth login`, and pick a region the subscription allows: `az account list-locations -o table` lists them.
2. Run `LOCATION=<region> bash infra/setup-local.sh`. [setup-local.sh](infra/setup-local.sh) generates the three database passwords and stores them as GitHub secrets without showing them, then runs [infra/setup.sh](infra/setup.sh): the resource group; the managed identity with a federated credential that trusts only workflow runs on `main` of this repository, and Contributor on this resource group; the SQL server with the "Allow Azure services" firewall rule and both databases; the Container Apps environment; the storage account with its static website switched on. It stores the identity's client id, the tenant id and the subscription id as GitHub secrets (identifiers, not passwords), opens the SQL firewall to its own IP only, creates one login per service with access to its own database only ([infra/create_sql_logins.py](infra/create_sql_logins.py)), and removes that firewall rule. Running it again changes nothing except rotating the database passwords.
3. Merge a pull request into `main`. After the first CD run, if the deploy job says an image is private: GitHub -> Packages -> `tabby-<service>` -> Package settings -> Change visibility -> Public, then re-run the job.

### Every merge to main

[cd.yml](.github/workflows/cd.yml) runs the whole CI workflow on the commit; only if it passes, it pushes both images tagged with the commit SHA, checks they are public, deploys them with [infra/deploy-service.sh](infra/deploy-service.sh) (creates each Container App the first time, then updates image and secret; the database URL is a Container Apps secret referenced by `DATABASE_URL`), publishes the UI to the storage account's `$web` container with a generated `config.js` holding the two service URLs ([infra/deploy-ui.sh](infra/deploy-ui.sh); the UI's address is the only origin the services allow in CORS), waits up to 5 minutes for each `/health` to return 200 with the new SHA ([infra/wait-healthy.sh](infra/wait-healthy.sh)), and prints the startup logs, including the migrations applied.

## API

Each service publishes its OpenAPI document at `/docs` and commits it as `openapi.json` ([ledger](services/ledger/openapi.json), [settlement](services/settlement/openapi.json)); a test fails if the file and the code disagree (`python -m tabby.openapi_export` regenerates it). Everything except `/health`, sign-up and login needs `Authorization: Bearer <token>`, where the token comes from sign-up or login.

| Service | Endpoints |
|---|---|
| ledger: accounts | `POST /api/signup`, `POST /api/login`, `POST /api/logout`, `GET /api/me`, `GET/POST /api/friends` |
| ledger: Domain A | `GET /api/groups/{id}/ledger` (called by settlement), `GET /api/categories`, `GET/POST /api/groups`, `GET /api/groups/{id}`, `POST /api/groups/{id}/members`, `DELETE /api/groups/{id}/members/{user_id}`, `GET/POST /api/groups/{id}/expenses`, `DELETE /api/groups/{id}/expenses/{expense_id}`, `GET /api/groups/{id}/spending` |
| settlement: Domain B | `GET /api/groups/{id}/settlement` (balances + suggested transfers), `GET/POST /api/groups/{id}/payments` |
| both | `GET /health` |

Money is always integer cents (`amount_cents`). An expense's `split_type` is `equal`, `shares` (each participant's `value` is a weight) or `exact` (each `value` is cents owed, adding up to the amount).

## Project structure

```
.github/workflows/ci.yml      lint, tests, contracts, image builds, e2e on compose
docker-compose.yml            sqlserver + db-init + ledger + settlement + ui (nginx)
db/init.sql                   local databases and logins (idempotent)
services/
  ledger/
    Dockerfile, app.py, requirements*.txt, openapi.json
    migrations/               001_init.sql, ...
    tabby/accounts/           users, sessions, friends
    tabby/ledger/             Domain A: groups, members, expenses, split rules, category seed
    tabby/db.py               connections, retries, migration runner
    tests/
  settlement/
    Dockerfile, app.py, requirements*.txt, openapi.json
    migrations/
    tabby/ledger_client.py    HTTP client for the ledger service (the seam)
    tabby/settlement/         Domain B: balances, greedy settle-up plan, payments
    tests/
tests/e2e/cross_seam.py       end-to-end test against the compose stack
ui/                           index.html, app.js, style.css, config.js
```

## Project docs

- [ADR.md](ADR.md): architecture decision log
- [AI_USAGE.md](AI_USAGE.md): AI usage log
- [docs/](docs): diagrams and reports
