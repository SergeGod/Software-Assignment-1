-- Migration 002: every expense gets the date the money was spent.
-- Until now the only date was created_at (when the row was typed in), so an
-- expense entered a week late looked a week younger than it was.
-- The table already holds rows, so the column is added in place:
--   1. add it as nullable, so existing rows are accepted;
--   2. backfill existing rows from the date part of created_at;
--   3. only then make it NOT NULL, with a default for inserts that omit it.
-- No row is deleted or recreated.

ALTER TABLE expenses ADD spent_on DATE NULL;
GO

-- A new batch: SQL Server compiles a batch before running it, so the column
-- must already exist when this UPDATE is compiled.
UPDATE expenses SET spent_on = CAST(created_at AS DATE) WHERE spent_on IS NULL;
GO

ALTER TABLE expenses ALTER COLUMN spent_on DATE NOT NULL;
ALTER TABLE expenses ADD CONSTRAINT df_expenses_spent_on
    DEFAULT CAST(SYSUTCDATETIME() AS DATE) FOR spent_on;
