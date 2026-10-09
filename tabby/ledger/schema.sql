-- Ledger domain tables. Applied on every boot by tabby/db.py:init_db().
-- Only CREATE ... IF NOT EXISTS: create what is missing, never drop or change data.
--
-- user_id / payer_id are ids from the accounts domain. They deliberately have
-- no FOREIGN KEY to users: the two domains must be able to live in separate
-- databases later, so membership is checked through accounts/interface.py.

CREATE TABLE IF NOT EXISTS expense_groups (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL REFERENCES expense_groups(id),
    user_id  INTEGER NOT NULL,
    PRIMARY KEY (group_id, user_id)
);

-- The composite foreign keys below point at group_members, so a member who
-- paid for or shares in any expense cannot be removed from the group.
CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY,
    group_id     INTEGER NOT NULL,
    payer_id     INTEGER NOT NULL,
    description  TEXT    NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    split_type   TEXT    NOT NULL CHECK (split_type IN ('equal', 'shares', 'exact')),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (group_id, payer_id) REFERENCES group_members(group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_group ON expenses(group_id);

-- What each participant owes for one expense, already rounded to whole cents.
-- The shares of one expense always add up to its amount_cents.
CREATE TABLE IF NOT EXISTS expense_shares (
    expense_id  INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    group_id    INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    share_cents INTEGER NOT NULL CHECK (share_cents >= 0),
    PRIMARY KEY (expense_id, user_id),
    FOREIGN KEY (group_id, user_id) REFERENCES group_members(group_id, user_id)
);
