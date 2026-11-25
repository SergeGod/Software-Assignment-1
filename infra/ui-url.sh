#!/usr/bin/env bash
# Prints the UI's public https URL without a trailing slash: this is also the
# origin the services allow in CORS.
set -euo pipefail
source "$(dirname "$0")/config.sh"
url=$(az storage account show -g "$RG" -n "$UI_STORAGE" --query primaryEndpoints.web -o tsv)
echo "${url%/}"
