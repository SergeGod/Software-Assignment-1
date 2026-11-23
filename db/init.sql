-- Local only: creates one database and one login per service, idempotently,
-- so it is safe on every `docker compose up`. Run by the db-init service with
-- sqlcmd, which fills in $(LEDGER_DB_PASSWORD) and $(SETTLEMENT_DB_PASSWORD).
-- On Azure the same logins are created once by infra/ (see the README).

IF DB_ID('ledger') IS NULL CREATE DATABASE ledger;
IF DB_ID('settlement') IS NULL CREATE DATABASE settlement;
GO

IF SUSER_ID('ledger_user') IS NULL
    CREATE LOGIN ledger_user WITH PASSWORD = '$(LEDGER_DB_PASSWORD)', CHECK_POLICY = OFF;
IF SUSER_ID('settlement_user') IS NULL
    CREATE LOGIN settlement_user WITH PASSWORD = '$(SETTLEMENT_DB_PASSWORD)', CHECK_POLICY = OFF;
GO

-- Each login is a user in its own database only, so ledger_user cannot read
-- settlement's tables and settlement_user cannot read ledger's. db_ddladmin
-- lets the service run its own migrations.
USE ledger;
GO
IF USER_ID('ledger_user') IS NULL CREATE USER ledger_user FOR LOGIN ledger_user;
ALTER ROLE db_ddladmin ADD MEMBER ledger_user;
ALTER ROLE db_datareader ADD MEMBER ledger_user;
ALTER ROLE db_datawriter ADD MEMBER ledger_user;
GO

USE settlement;
GO
IF USER_ID('settlement_user') IS NULL CREATE USER settlement_user FOR LOGIN settlement_user;
ALTER ROLE db_ddladmin ADD MEMBER settlement_user;
ALTER ROLE db_datareader ADD MEMBER settlement_user;
ALTER ROLE db_datawriter ADD MEMBER settlement_user;
GO
