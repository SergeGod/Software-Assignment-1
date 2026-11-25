#!/usr/bin/env bash
# The one-time Azure setup, run from a laptop:
#   LOCATION=<region> bash infra/setup-local.sh
# where <region> is one your Azure for Students subscription allows.
#   1. generates the three database passwords and stores them as GitHub
#      secrets, without printing them;
#   2. runs infra/setup.sh (resource group, the pipeline's identity, SQL
#      server and databases, Container Apps environment, UI storage);
#   3. stores the identity's ids as GitHub secrets (they are identifiers, not
#      passwords: nothing can sign in with them alone);
#   4. creates one SQL login per service, opening the SQL firewall to this
#      machine's IP only while it does so.
# Needs: az and gh (both logged in), and services/ledger/.venv with pymssql.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source infra/config.sh; set +a
: "${LOCATION:?set LOCATION to a region your subscription allows}"
export LOCATION

echo "Subscription: $(az account show --query name -o tsv)"

for name in SQL_ADMIN_PASSWORD LEDGER_DB_PASSWORD SETTLEMENT_DB_PASSWORD; do
  value="Tb_$(openssl rand -hex 16)"
  printf '%s' "$value" | gh secret set "$name" > /dev/null
  export "$name=$value"
  echo "GitHub secret $name set"
done

bash infra/setup.sh

az identity show -g "$RG" -n "$IDENTITY" --query clientId -o tsv | tr -d '\n' | gh secret set AZURE_CLIENT_ID > /dev/null
az account show --query tenantId -o tsv | tr -d '\n' | gh secret set AZURE_TENANT_ID > /dev/null
az account show --query id -o tsv | tr -d '\n' | gh secret set AZURE_SUBSCRIPTION_ID > /dev/null
echo "GitHub secrets AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID set"

ip=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n local-setup \
  --start-ip-address "$ip" --end-ip-address "$ip" --output none
trap 'az sql server firewall-rule delete -g "$RG" -s "$SQL_SERVER" -n local-setup --output none || true' EXIT
sleep 15   # a new firewall rule takes a few seconds to apply
services/ledger/.venv/bin/python infra/create_sql_logins.py

echo "Azure setup finished."
