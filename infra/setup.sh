#!/usr/bin/env bash
# One-time Azure setup, run from a laptop by infra/setup-local.sh.
# Idempotent: every step checks first, so running it again changes nothing.
# Needs: az logged in to the Azure for Students subscription, LOCATION (one of
# the regions the subscription allows) and SQL_ADMIN_PASSWORD in the environment.
set -euo pipefail
source "$(dirname "$0")/config.sh"

# A new subscription has no resource providers registered yet.
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace "$provider" --wait --output none
done

# --- Resource group: everything of this system, and nothing else ---
if ! az group show -n "$RG" > /dev/null 2>&1; then
  az group create -n "$RG" -l "$LOCATION" --output none
fi
LOCATION=$(az group show -n "$RG" --query location -o tsv)
RG_ID=$(az group show -n "$RG" --query id -o tsv)
echo "Resource group $RG is in $LOCATION"

# --- The pipeline's identity: OpenID Connect, no password anywhere ---
if ! az identity show -g "$RG" -n "$IDENTITY" > /dev/null 2>&1; then
  az identity create -g "$RG" -n "$IDENTITY" -l "$LOCATION" --output none
fi
# Azure accepts a GitHub token only if it was issued to a workflow run on the
# main branch of this repository: no other branch, pull request or repository.
az identity federated-credential create -g "$RG" --identity-name "$IDENTITY" --name github-main \
  --issuer https://token.actions.githubusercontent.com \
  --subject "repo:$GITHUB_REPO:ref:refs/heads/main" \
  --audiences api://AzureADTokenExchange --output none
# Contributor on this resource group only: it can deploy here and nowhere else.
principal=$(az identity show -g "$RG" -n "$IDENTITY" --query principalId -o tsv)
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID" --output none

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
    # General Purpose serverless, Gen5, 0.5-1 vCore, locally redundant backups,
    # on Azure SQL's free offer: the offer itself fixes the auto-pause delay and
    # the 32 GB size (so they are not passed), and the database pauses instead
    # of billing when the monthly free amount is used up (§7).
    az sql db create -g "$RG" -s "$SQL_SERVER" -n "$db" \
      --edition GeneralPurpose --compute-model Serverless --family Gen5 \
      --min-capacity 0.5 --capacity 1 \
      --use-free-limit true --free-limit-exhaustion-behavior AutoPause \
      --backup-storage-redundancy Local --output none
  fi
done

# --- Container Apps environment (Consumption) ---
# Azure creates a Log Analytics workspace with it, which keeps the containers'
# logs (pay-per-use, free up to 5 GB a month).
if ! az containerapp env show -g "$RG" -n "$ENVIRONMENT" > /dev/null 2>&1; then
  az containerapp env create -g "$RG" -n "$ENVIRONMENT" -l "$LOCATION" --output none
fi

# --- Static UI: a storage account with the static website feature ---
# Standard locally redundant storage is billed per GB stored and per request;
# three small files cost a fraction of a cent per month.
if ! az storage account show -g "$RG" -n "$UI_STORAGE" > /dev/null 2>&1; then
  az storage account create -g "$RG" -n "$UI_STORAGE" -l "$LOCATION" \
    --sku Standard_LRS --kind StorageV2 --https-only true --min-tls-version TLS1_2 --output none
fi
# Serves the files uploaded to the $web container at the account's web endpoint.
az storage blob service-properties update --account-name "$UI_STORAGE" --auth-mode key \
  --static-website --index-document index.html --404-document index.html --output none

echo "Setup done. Next: the SQL logins (infra/create_sql_logins.py)."
