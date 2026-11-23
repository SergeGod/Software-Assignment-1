#!/usr/bin/env bash
# One-time Azure setup, run by .github/workflows/azure-setup.yml (manual trigger).
# Idempotent: every step checks first, so running it again changes nothing.
# Needs: az logged in, SQL_ADMIN_PASSWORD in the environment.
set -euo pipefail
source "$(dirname "$0")/config.sh"

LOCATION=$(az group show -n "$RG" --query location -o tsv)
echo "Resource group $RG is in $LOCATION"

# --- Azure SQL: one logical server, one serverless database per service ---
if ! az sql server show -g "$RG" -n "$SQL_SERVER" > /dev/null 2>&1; then
  az sql server create -g "$RG" -n "$SQL_SERVER" -l "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_ADMIN_PASSWORD" --output none
fi
# "Allow Azure services": the special 0.0.0.0 rule lets Container Apps connect.
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none

for service in $SERVICES; do
  db="$PREFIX-$service-db"
  if ! az sql db show -g "$RG" -s "$SQL_SERVER" -n "$db" > /dev/null 2>&1; then
    # General Purpose serverless, Gen5, 0.5-1 vCore, pauses after the shortest
    # delay Azure allows, 2 GB max, locally redundant backups (§7).
    az sql db create -g "$RG" -s "$SQL_SERVER" -n "$db" \
      --edition GeneralPurpose --compute-model Serverless --family Gen5 \
      --min-capacity 0.5 --capacity 1 --auto-pause-delay "${AUTO_PAUSE_MINUTES:-15}" \
      --max-size 2GB --backup-storage-redundancy Local --output none
  fi
done

# --- Container Apps environment (Consumption) ---
if ! az containerapp env show -g "$RG" -n "$ENVIRONMENT" > /dev/null 2>&1; then
  az containerapp env create -g "$RG" -n "$ENVIRONMENT" -l "$LOCATION" \
    --logs-destination none --output none
fi

echo "Setup done. Next: the SQL logins (infra/create_sql_logins.py)."
