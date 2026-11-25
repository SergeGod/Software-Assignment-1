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
# General Purpose serverless, Gen5, 0.5 vCore minimum, locally redundant
# backups, on Azure SQL's free offer (§7). The free offer is not accepted in
# every region or for every size, and Azure only says so when the database is
# created, so this tries in order: the group's region first, then the other
# regions the subscription allows; in each, 1 vCore maximum (what §7 asks) and
# then 2 (what Microsoft's own example uses). The SQL server may end up in a
# different region from the rest; that only adds a few milliseconds per query.
create_db() {  # create_db <name> <max vCores> <free|paid>
  local extra=(--use-free-limit true --free-limit-exhaustion-behavior AutoPause)
  [[ $3 == paid ]] && extra=(--auto-pause-delay 60 --max-size 32GB)
  az sql db create -g "$RG" -s "$SQL_SERVER" -n "$1" \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 \
    --min-capacity 0.5 --capacity "$2" "${extra[@]}" \
    --backup-storage-redundancy Local --output none
}
db_exists() { az sql db show -g "$RG" -s "$SQL_SERVER" -n "$1" > /dev/null 2>&1; }
user_db_count() {
  az sql db list -g "$RG" -s "$SQL_SERVER" --query "length([?name!='master'])" -o tsv 2>/dev/null || echo 0
}
ensure_server() {  # ensure_server <region>: the server exists in that region
  local current
  current=$(az sql server show -g "$RG" -n "$SQL_SERVER" --query location -o tsv 2>/dev/null || true)
  if [[ -n $current && $current != "$1" ]]; then
    # Only ever removes a server that holds no database of ours.
    [[ $(user_db_count) == 0 ]] || return 1
    echo "Moving the empty SQL server from $current to $1"
    az sql server delete -g "$RG" -n "$SQL_SERVER" --yes --output none
    current=""
  fi
  if [[ -z $current ]]; then
    # A deleted server's name takes a few minutes to become free again.
    for try in $(seq 1 20); do
      az sql server create -g "$RG" -n "$SQL_SERVER" -l "$1" --admin-user "$SQL_ADMIN" \
        --admin-password "$SQL_ADMIN_PASSWORD" --output none 2>/dev/null && break
      [[ $try == 20 ]] && return 1
      sleep 30
    done
  fi
  # "Allow Azure services": the special 0.0.0.0 rule lets Container Apps connect.
  az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
    --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
}

first_db="$PREFIX-${SERVICES%% *}-db"
chosen=""
if db_exists "$first_db"; then
  chosen=existing
elif [[ ${SQL_OFFER:-free} == paid ]]; then
  # SQL_OFFER=paid skips the search: serverless databases on the credit.
  ensure_server "$LOCATION"
  create_db "$first_db" 1 paid
  chosen="1 paid"
else
  for region in $LOCATION ${SQL_REGIONS:-switzerlandnorth germanywestcentral belgiumcentral denmarkeast spaincentral}; do
    ensure_server "$region" || continue
    for vcores in 1 2; do
      echo "Trying a free-offer database in $region with $vcores vCore(s) maximum"
      if create_db "$first_db" "$vcores" free 2>/dev/null; then
        chosen="$vcores free"
        break 2
      fi
    done
  done
fi
if [[ -z $chosen ]]; then
  # Last resort so the system can run at all: the same serverless database
  # without the free offer, paid from the Azure for Students credit.
  echo "The free offer was refused everywhere; creating paid serverless databases (1 vCore, auto-pause 60 min)"
  ensure_server "$LOCATION"
  create_db "$first_db" 1 paid
  chosen="1 paid"
fi
echo "SQL server is in $(az sql server show -g "$RG" -n "$SQL_SERVER" --query location -o tsv); first database: $chosen"

for service in $SERVICES; do
  db="$PREFIX-$service-db"
  db_exists "$db" && continue
  if [[ $chosen == existing ]]; then
    create_db "$db" 1 free 2>/dev/null || create_db "$db" 2 free 2>/dev/null || create_db "$db" 1 paid
  else
    create_db "$db" $chosen
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
