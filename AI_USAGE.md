# AI Usage Log

One row per meaningful interaction with an AI tool. The last column is my own explanation of how the accepted code works.

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|
| 2026-10-08 / a3e48d6, 68f679b | Claude Code (Claude Opus 5.5) | Read the assignment spec, propose app ideas with two separable domains, compare Flask and FastAPI, then build Step 1: Python `.gitignore`, pinned `requirements.txt`, an app skeleton that reads `PORT` and `DATA_DIR`, binds `0.0.0.0` and creates its SQLite schema on first boot without dropping tables, ADR-1, this log and a README skeleton. | Modified | Rejected the first four app ideas (gym tracker, recipe box, event booking, link shortener) as too simple and asked for something more substantial; picked the expense splitter from the second set. Accepted the recommended FastAPI, stdlib `sqlite3` and package-per-domain layout. Picked the name "Tabby" instead of the recommended "FairShare". | _TODO (me)_ |
