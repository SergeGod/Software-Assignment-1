# Architecture Decision Records

Lightweight log of the main design decisions for Tabby, added as each decision is made.

## 1. Backend stack: Python + FastAPI with stdlib sqlite3
Date: 2026-10-08  
Status: Decided  
Context: Tabby is an API plus a small web page that lets flatmates and trip groups (pilot user: a student housing co-op with about 400 shared flats) log shared expenses and settle up. Most bugs in an expense app come from bad input such as negative amounts, splits that do not add up, or unknown members, and in Assignment 2 the two domains become separate services that need a written API contract. Python is the language I already work in, and the provided container template targets python:3.12-slim.  
Decision: Python 3.12 with FastAPI, served by a single uvicorn process started with `python app.py`, talking to SQLite through Python's built-in `sqlite3` module and a hand-written `schema.sql` instead of an ORM.  
Alternatives considered: Flask was simpler, but every route would need hand-written validation and there would be no generated API docs to act as the contract between domains. Django brings an admin, auth system and ORM this app does not need. SQLAlchemy is a large dependency for about five tables and would hide the schema that ADR-3 has to defend.  
Consequences: Pydantic models reject bad input before our code runs, `/docs` publishes each domain's API, and one APIRouter per domain keeps the seam visible. In exchange we write and test all SQL by hand, and endpoints stay plain `def` (not `async def`) because `sqlite3` calls block.
