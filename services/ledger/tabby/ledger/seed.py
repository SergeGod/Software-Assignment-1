"""Loads the starter expense categories from seed_categories.csv on first boot."""

import csv
from pathlib import Path

from tabby.db import Connection

SEED_FILE = Path(__file__).resolve().parent / "seed_categories.csv"


def seed_categories(conn: Connection, seed_file: Path = SEED_FILE) -> int:
    """Insert the categories only if the table is empty. Returns how many were inserted.

    The guard makes this idempotent: on every later boot the table already has
    rows, so nothing is inserted twice and categories users rely on stay put.
    """
    if conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"] > 0:
        return 0
    with seed_file.open(newline="") as f:
        names = [row["name"].strip() for row in csv.DictReader(f) if row["name"].strip()]
    with conn:
        conn.executemany("INSERT INTO categories (name) VALUES (%s)", [(n,) for n in names])
    return len(names)
