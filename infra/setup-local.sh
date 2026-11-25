#!/usr/bin/env bash
# The one-time Azure setup, run from a laptop with your own `az login`
# (your IE account has Contributor on the class resource group) instead of
# through azure-setup.yml. Does the same steps as that workflow:
#   1. generates the three database passwords and stores them as GitHub
#      secrets, without printing them;
#   2. runs infra/setup.sh (SQL server, databases, environment, UI storage);
#   3. creates one SQL login per service, opening the SQL firewall to this
#      machine's IP only while it does so.
# Needs: az (logged in), gh (logged in), and services/ledger/.venv with pymssql.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source infra/config.sh; set +a

for name in SQL_ADMIN_PASSWORD LEDGER_DB_PASSWORD SETTLEMENT_DB_PASSWORD; do
  value="Tb_$(openssl rand -hex 16)"
  printf '%s' "$value" | gh secret set "$name" > /dev/null
  export "$name=$value"
  echo "GitHub secret $name set"
done

bash infra/setup.sh

ip=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n local-setup \
  --start-ip-address "$ip" --end-ip-address "$ip" --output none
trap 'az sql server firewall-rule delete -g "$RG" -s "$SQL_SERVER" -n local-setup --output none || true' EXIT
sleep 15   # a new firewall rule takes a few seconds to apply
services/ledger/.venv/bin/python infra/create_sql_logins.py

echo "Azure setup finished."
