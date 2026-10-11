-- Settlement domain tables. Applied on every boot by tabby/db.py:init_db().
-- Only CREATE ... IF NOT EXISTS: create what is missing, never drop or change data.
--
-- group_id and the user ids come from the ledger and accounts domains, so they
-- have no FOREIGN KEY (see ADR-2); membership is checked via ledger/interface.py.

-- A real-world payment between two group members ("I paid Bob 20 euros").
CREATE TABLE IF NOT EXISTS payments (
    id           INTEGER PRIMARY KEY,
    group_id     INTEGER NOT NULL,
    from_user_id INTEGER NOT NULL,
    to_user_id   INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (from_user_id <> to_user_id)
);

CREATE INDEX IF NOT EXISTS idx_payments_group ON payments(group_id);
