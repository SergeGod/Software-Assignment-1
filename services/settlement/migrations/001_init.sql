-- 001: the settlement tables, ported from the Assignment 1 SQLite schema.
-- Applied once by tabby/db.py:migrate() and recorded in schema_migrations.
--
-- group_id and the user ids come from the ledger service's database, so they
-- have no FOREIGN KEY (ADR-2, ADR-7); the ledger service checks membership
-- whenever settlement asks it for a group's ledger.

-- A real-world payment between two group members ("I paid Bob 20 euros").
CREATE TABLE payments (
    id           INT IDENTITY PRIMARY KEY,
    group_id     INT       NOT NULL,
    from_user_id INT       NOT NULL,
    to_user_id   INT       NOT NULL,
    amount_cents INT       NOT NULL CHECK (amount_cents > 0),
    created_at   DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CHECK (from_user_id <> to_user_id)
);

CREATE INDEX idx_payments_group ON payments(group_id);

-- One row that GET /health updates and reads back, to prove the service can
-- both write and read its own database.
CREATE TABLE service_heartbeat (
    id         INT       NOT NULL PRIMARY KEY CHECK (id = 1),
    checked_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
INSERT INTO service_heartbeat (id) VALUES (1);
