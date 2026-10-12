# Architecture Decision Records

Lightweight log of the main design decisions for Tabby, added as each decision is made.

## 1. Backend stack: Python + FastAPI with stdlib sqlite3
Date: 2026-10-08  
Status: Decided  
Context: Tabby is an API plus a small web page that lets flatmates and trip groups (pilot user: a student housing co-op with about 400 shared flats) log shared expenses and settle up. Most bugs in an expense app come from bad input such as negative amounts, splits that do not add up, or unknown members, and in Assignment 2 the two domains become separate services that need a written API contract. Python is the language I already work in, and the provided container template targets python:3.12-slim.  
Decision: Python 3.12 with FastAPI, served by a single uvicorn process started with `python app.py`, talking to SQLite through Python's built-in `sqlite3` module and a hand-written `schema.sql` instead of an ORM.  
Alternatives considered: Flask was simpler, but every route would need hand-written validation and there would be no generated API docs to act as the contract between domains. Django brings an admin, auth system and ORM this app does not need. SQLAlchemy is a large dependency for about five tables and would hide the schema that ADR-3 has to defend.  
Consequences: Pydantic models reject bad input before our code runs, `/docs` publishes each domain's API, and one APIRouter per domain keeps the seam visible. In exchange we write and test all SQL by hand, and endpoints stay plain `def` (not `async def`) because `sqlite3` calls block.

## 2. Domain seam: other domains only use a domain's interface.py
Date: 2026-10-09  
Status: Decided  
Context: Tabby has two feature domains, the ledger (Domain A: groups, members, expenses) and settlement (Domain B: balances and the fewest transfers to settle up), plus an accounts domain for login and friends that both rely on. In Assignment 2 they become separate services, so each one must be liftable without rewriting the others.  
Decision: Each domain is its own package (`tabby/accounts`, `tabby/ledger`, `tabby/settlement`) with its own routes, service, repository and `schema.sql`, and other domains may only import its `interface.py`. Settlement reads expense data only through `ledger.interface.get_group_ledger(group_id)`, which returns plain dataclasses, and ids from another domain (such as `user_id`) are stored as plain integers with no foreign key.  
Alternatives considered: Letting settlement run SQL joins directly on `expenses` and `expense_shares` would be less code, but both domains would then depend on the same tables and the split would mean rewriting settlement. Having the ledger push every expense into a settlement-owned table is closest to event-driven microservices, but it duplicates data that can drift out of sync, which is not worth it inside one process.  
Consequences: In Assignment 2 the cut is a handful of functions: `get_group_ledger` becomes `GET /groups/{id}/ledger` and `current_user`/`are_friends` become calls to an accounts service. The cost is that settlement cannot join across domains, and the database cannot enforce that a `user_id` stored in the ledger really exists.

## 3. Schema: money as integer cents, splits stored as resolved per-member shares
Date: 2026-10-11  
Status: Decided  
Context: Settlement (Domain B) has to know exactly how much each person owes for every expense in the ledger (Domain A), but expenses can be split three ways (equal, shares, exact) and dividing money creates rounding. Floating-point numbers cannot represent most cent values exactly (`0.1 + 0.2 != 0.3`), so balances could drift by fractions of a cent.  
Decision: Every amount is an `INTEGER` number of cents, and each expense is resolved once, when it is saved, into one `expense_shares` row per participant whose `share_cents` always add up to `expenses.amount_cents`. Settlement's `payments` table relates to the ledger tables only through plain `group_id` and user ids, with no cross-domain foreign keys (ADR-2).  
Alternatives considered: Storing euros as `REAL` was rejected because of floating-point rounding errors in sums. Storing only the split inputs (type and weights) on the expense and recomputing shares on every read would save a table, but every reader, including a future settlement service, would need a copy of the split and rounding rules, which duplicates ledger logic across the seam.  
Consequences: Settlement only sums integers and never needs the ledger's split rules, and the per-member rows enable the composite foreign key that stops a member with expenses from being removed. The original weights (e.g. 2:1:1) are not kept, and because `CREATE TABLE IF NOT EXISTS` never changes an existing table, future column changes will need explicit `ALTER TABLE` migrations.

## 4. Testing: pure logic plus services against a real temporary SQLite file
Date: 2026-10-11  
Status: Decided  
Context: §4 asks for at least 70% coverage of the core business logic of both domains. In Tabby the riskiest code is money and access: the rounding in `splits.py`, the greedy plan in `engine.py`, password and session handling, and the service rules about who may see, pay or remove whom.  
Decision: Pure functions are tested directly, including property-style checks (every split adds up to the amount for 299 amounts, and 50 random groups each settle in at most n - 1 transfers). Services are tested against a fresh SQLite file per test through the `conn` fixture in `tests/conftest.py`, and coverage is measured over the whole `tabby` package with `pytest --cov=tabby` (94%).  
Alternatives considered: Driving every endpoint through FastAPI's `TestClient` would raise coverage quickly, but it mostly tests routing glue FastAPI already tests and needs `httpx` as an extra package. Mocking the database would be faster, but it would not catch real SQL or constraint bugs such as the composite foreign key that blocks removing a used member.  
Consequences: Every business-logic module is at 100%, and the suite already caught a real bug (a negative `SESSION_DAYS` crashed session creation). The HTTP layer (route bodies, the cookie check in `current_user`, `get_conn`) and the frontend JavaScript are only covered by manual and browser testing.

## 5. Not built: friend requests (adding a friend is instant and mutual)
Date: 2026-10-12  
Status: Decided  
Context: Groups can only be built from friends, so friendship decides who can put you in a group and assign expenses to you. The pilot users are flatmates and trip groups who already know each other's usernames, and the whole project had four days.  
Decision: Adding a friend by exact username creates the friendship immediately for both people (one row in `friendships`), with no request, accept/decline or block flow.  
Alternatives considered: A request/accept flow (a pending/accepted/declined status, an inbox screen, accept and decline endpoints) is safer, but it adds a state machine, more endpoints and UI for a risk the pilot does not have, and would have cost the time spent on settlement and tests. Dropping friends and inviting people into groups directly by username is even simpler, but it removes the only check on who can add you to a group.  
Consequences: Anyone who knows your username can befriend you and add you to a group, so friend requests must be built before Tabby is opened beyond trusted groups. Because each friendship is already one ordered row, this later becomes a `status` column plus two endpoints rather than a redesign.
