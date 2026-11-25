// Where the browser finds the two services. This file is for local runs
// (docker compose publishes ledger on 8001 and settlement on 8002); the CD
// pipeline generates its own copy with the Azure Container Apps URLs when it
// publishes the UI (infra/deploy-ui.sh).
window.TABBY_CONFIG = {
  ledgerUrl: "http://localhost:8001",
  settlementUrl: "http://localhost:8002",
  coldStarts: false,
};
