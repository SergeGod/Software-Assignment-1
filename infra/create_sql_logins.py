"""One-time: create one login per service on the Azure SQL server and make it
a user of its own database only (the same rights as db/init.sql locally).

Run by infra/setup-local.sh with SQL_ADMIN_PASSWORD,
LEDGER_DB_PASSWORD and SETTLEMENT_DB_PASSWORD in the environment. Idempotent:
an existing login gets its password reset to the current secret, which is
also how a leaked database password is rotated.
"""

import os
import re

import pymssql

# Exported from infra/config.sh by the workflow (set -a; source infra/config.sh).
CONFIG = {name: os.environ[name] for name in ("PREFIX", "SQL_SERVER", "SQL_ADMIN", "SERVICES")}
SERVER = f"{CONFIG['SQL_SERVER']}.database.windows.net"
# DDL cannot take parameters, so only passwords that are safe inside quotes are accepted.
SAFE = re.compile(r"^[A-Za-z0-9_]{12,128}$")


def connect(database: str) -> pymssql.Connection:
    return pymssql.connect(
        server=SERVER, user=f"{CONFIG['SQL_ADMIN']}@{CONFIG['SQL_SERVER']}", password=os.environ["SQL_ADMIN_PASSWORD"],
        database=database, autocommit=True, tds_version="7.4", login_timeout=30,
    )


def main() -> None:
    services = CONFIG["SERVICES"].split()
    passwords = {s: os.environ[f"{s.upper()}_DB_PASSWORD"] for s in services}
    for service, password in passwords.items():
        if not SAFE.match(password):
            raise SystemExit(f"{service.upper()}_DB_PASSWORD must be 12+ letters, digits or _")

    with connect("master") as conn:
        cursor = conn.cursor()
        for service, password in passwords.items():
            login = f"{service}_user"
            cursor.execute(
                f"IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = '{login}') "
                f"CREATE LOGIN [{login}] WITH PASSWORD = '{password}' "
                f"ELSE ALTER LOGIN [{login}] WITH PASSWORD = '{password}'"
            )
            print(f"login {login}: ok")

    for service in passwords:
        login = f"{service}_user"
        with connect(f"{CONFIG['PREFIX']}-{service}-db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"IF USER_ID('{login}') IS NULL CREATE USER [{login}] FOR LOGIN [{login}]"
            )
            for role in ("db_ddladmin", "db_datareader", "db_datawriter"):
                cursor.execute(f"ALTER ROLE {role} ADD MEMBER [{login}]")
            print(f"user {login} in {CONFIG['PREFIX']}-{service}-db: ok")


if __name__ == "__main__":
    main()
