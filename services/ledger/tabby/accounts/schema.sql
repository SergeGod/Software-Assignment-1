-- Accounts domain tables. Applied on every boot by tabby/db.py:init_db().
-- Only CREATE ... IF NOT EXISTS: create what is missing, never drop or change data.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    display_name  TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- We store a SHA-256 of the session token, never the token itself.
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL
);

-- One row per friendship, stored with the smaller id first.
CREATE TABLE IF NOT EXISTS friendships (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id),
    CHECK (user_id < friend_id)
);
