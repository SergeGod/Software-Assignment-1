// Where the browser finds the two services. This file is for local runs
// (docker compose publishes ledger on 8001 and settlement on 8002); the CD
// pipeline overwrites it with the Azure Container Apps URLs before deploying
// the UI to Static Web Apps.
window.TABBY_CONFIG = {
  ledgerUrl: "http://localhost:8001",
  settlementUrl: "http://localhost:8002",
};
