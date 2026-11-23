#!/usr/bin/env bash
# Deploys one service image to its Container App: creates the app on the first
# deploy, updates image, secret and settings afterwards. Run by cd.yml.
#   infra/deploy-service.sh <ledger|settlement> <image:sha>
# Needs: az logged in; <SERVICE>_DB_PASSWORD and UI_ORIGIN in the environment;
# LEDGER_URL as well for settlement. Prints the app's https URL on the last line.
set -euo pipefail
source "$(dirname "$0")/config.sh"

service=$1
image=$2
app="$PREFIX-$service"
password_var="${service^^}_DB_PASSWORD"
password="${!password_var}"

# The connection string is a Container Apps secret, referenced by the env var,
# so it never appears as a plain environment variable.
# Azure SQL accepts the login as user@servername (%40 is @ inside a URL); the
# pymssql docs recommend that form for Azure.
database_url="mssql://${service}_user%40${SQL_SERVER}:${password}@${SQL_SERVER}.database.windows.net:1433/${PREFIX}-${service}-db"

env_vars=(DATABASE_URL=secretref:database-url "CORS_ORIGINS=$UI_ORIGIN")
if [[ $service == settlement ]]; then
  # Longer than locally (5 s): ledger may be starting from zero replicas.
  env_vars+=("LEDGER_URL=$LEDGER_URL" "LEDGER_TIMEOUT_S=20")
fi

if az containerapp show -g "$RG" -n "$app" > /dev/null 2>&1; then
  az containerapp secret set -g "$RG" -n "$app" --secrets "database-url=$database_url" --output none
  az containerapp update -g "$RG" -n "$app" --image "$image" \
    --min-replicas 0 --max-replicas 1 --set-env-vars "${env_vars[@]}" --output none
else
  # Consumption plan, scale to zero, at most one replica so migrations at
  # startup never run twice at the same time (§7).
  az containerapp create -g "$RG" -n "$app" --environment "$ENVIRONMENT" --image "$image" \
    --ingress external --target-port 8000 --cpu 0.25 --memory 0.5Gi \
    --min-replicas 0 --max-replicas 1 \
    --secrets "database-url=$database_url" --env-vars "${env_vars[@]}" --output none
fi

echo "https://$(az containerapp show -g "$RG" -n "$app" --query properties.configuration.ingress.fqdn -o tsv)"
