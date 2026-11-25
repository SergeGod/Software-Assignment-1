# Names of every Azure resource, sourced by the other infra scripts.
# Everything lives in one resource group in my own Azure for Students
# subscription, and every name starts with the prefix (§7).
PREFIX=shagopian-ieu2024
RG=rg-$PREFIX
ENVIRONMENT=$PREFIX-env
SQL_SERVER=$PREFIX-sql
SQL_ADMIN=tabbyadmin
SERVICES="ledger settlement"
# Storage account names allow no hyphens: the prefix without them, plus "ui".
UI_STORAGE=${PREFIX//-/}ui
# The identity the pipeline signs in as (OpenID Connect, no stored password),
# trusted only for runs on main of this repository.
IDENTITY=$PREFIX-github
GITHUB_REPO=SergeGod/Software-Assignment-1
