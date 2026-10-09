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
