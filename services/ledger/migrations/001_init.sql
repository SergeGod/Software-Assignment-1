-- 001: the accounts and ledger tables, ported from the Assignment 1 SQLite schema.
-- Applied once by tabby/db.py:migrate() and recorded in schema_migrations.
--
-- SQLite -> SQL Server: INTEGER PRIMARY KEY -> INT IDENTITY, TEXT -> NVARCHAR,
-- datetime('now') -> SYSUTCDATETIME() in a DATETIME2 column.

-- ---------- accounts ----------

CREATE TABLE users (
    id            INT IDENTITY  PRIMARY KEY,
    username      NVARCHAR(30)  NOT NULL UNIQUE,
    display_name  NVARCHAR(50)  NOT NULL,
    password_hash NVARCHAR(255) NOT NULL,
    created_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);

-- We store a SHA-256 of the session token, never the token itself.
CREATE TABLE sessions (
    token_hash CHAR(64)  NOT NULL PRIMARY KEY,
    user_id    INT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at DATETIME2 NOT NULL
);

-- One row per friendship, stored with the smaller id first.
-- No ON DELETE CASCADE here: SQL Server refuses two cascade paths from one
-- table to users (error 1785), and users are never deleted anyway.
CREATE TABLE friendships (
    user_id    INT       NOT NULL REFERENCES users(id),
    friend_id  INT       NOT NULL REFERENCES users(id),
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    PRIMARY KEY (user_id, friend_id),
    CHECK (user_id < friend_id)
);

-- ---------- ledger ----------
-- user_id / payer_id are ids from the accounts domain. They have no FOREIGN KEY
-- to users, as in Assignment 1 (ADR-2), so the two domains stay separable.

-- Reference data, filled from seed_categories.csv when empty (see seed.py).
CREATE TABLE categories (
    id   INT IDENTITY PRIMARY KEY,
    name NVARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE expense_groups (
    id         INT IDENTITY PRIMARY KEY,
    name       NVARCHAR(80) NOT NULL,
    created_at DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE group_members (
    group_id INT NOT NULL REFERENCES expense_groups(id),
    user_id  INT NOT NULL,
    PRIMARY KEY (group_id, user_id)
);

-- The composite foreign keys below point at group_members, so a member who
-- paid for or shares in any expense cannot be removed from the group.
CREATE TABLE expenses (
    id           INT IDENTITY  PRIMARY KEY,
    group_id     INT           NOT NULL,
    payer_id     INT           NOT NULL,
    description  NVARCHAR(200) NOT NULL,
    amount_cents INT           NOT NULL CHECK (amount_cents > 0),
    split_type   NVARCHAR(10)  NOT NULL CHECK (split_type IN ('equal', 'shares', 'exact')),
    category_id  INT           NOT NULL REFERENCES categories(id),
    created_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    FOREIGN KEY (group_id, payer_id) REFERENCES group_members(group_id, user_id)
);

CREATE INDEX idx_expenses_group ON expenses(group_id);

-- What each participant owes for one expense, already rounded to whole cents.
-- The shares of one expense always add up to its amount_cents.
CREATE TABLE expense_shares (
    expense_id  INT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    group_id    INT NOT NULL,
    user_id     INT NOT NULL,
    share_cents INT NOT NULL CHECK (share_cents >= 0),
    PRIMARY KEY (expense_id, user_id),
    FOREIGN KEY (group_id, user_id) REFERENCES group_members(group_id, user_id)
);

-- ---------- operations ----------

-- One row that GET /health updates and reads back, to prove the service can
-- both write and read its own database.
CREATE TABLE service_heartbeat (
    id         INT       NOT NULL PRIMARY KEY CHECK (id = 1),
    checked_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
INSERT INTO service_heartbeat (id) VALUES (1);
