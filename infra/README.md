# CI/CD PoC infrastructure

This is the first, intentionally low-cost infrastructure phase.

## What it creates

- 1 disposable Resource Group
- 1 Linux App Service Plan (F1 Free, shared compute)
- 4 Linux Web Apps on the same plan:
  - DEV
  - UAT
  - PROD
  - DR

This phase intentionally does **not** create:

- PROD deployment slots
- VNet / Private Endpoint / Private DNS
- self-hosted agents
- Application Insights / Log Analytics
- Key Vault
- Front Door / Application Gateway

The purpose is to validate the CI/CD flow with Microsoft-hosted agents at minimum cost.

Each app receives a runtime `APP_ENV` setting so the pipeline can distinguish the target environment.

## Validate

```bash
az bicep build --file infra/main.bicep
```

## Preview

```bash
az deployment sub what-if \
  --location japaneast \
  --name cicd-demo-poc \
  --template-file infra/main.bicep \
  --parameters infra/poc.bicepparam
```

## Deploy

```bash
az deployment sub create \
  --location japaneast \
  --name cicd-demo-poc \
  --template-file infra/main.bicep \
  --parameters infra/poc.bicepparam
```

Show the generated Web App names and URLs:

```bash
az deployment sub show \
  --name cicd-demo-poc \
  --query properties.outputs \
  --output json
```

## Delete after the PoC

The Resource Group exists only for this PoC. Delete the whole group when the validation is complete so the App Service Plan stops incurring cost.

```bash
az group delete \
  --name rg-cicd-demo-poc-jpe \
  --yes
```

## Phase 2

Only after the public/Microsoft-hosted flow is proven:

1. upgrade the App Service Plan to a SKU that supports slots;
2. add the PROD staging slot;
3. validate staging deploy -> smoke -> swap -> production smoke;
4. add PROD/staging Private Endpoints and Private DNS;
5. temporarily add a self-hosted agent and validate App + SCM private deployment paths;
6. delete the temporary resources or return to F1 after the test.
