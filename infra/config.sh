# Names of every Azure resource, sourced by the other infra scripts.
# Every name starts with the prefix (§7); the resource group already exists.
PREFIX=shagopian-ieu2024
RG=rg-sdd-3b
ENVIRONMENT=$PREFIX-env
SQL_SERVER=$PREFIX-sql
SQL_ADMIN=tabbyadmin
SERVICES="ledger settlement"
# Storage account names allow no hyphens: the prefix without them, plus "ui".
UI_STORAGE=${PREFIX//-/}ui
