# Chat to Azure Pipelines Bridge

Bridge workflow:
.github/workflows/azure-pipelines-bridge.yml

Control issue:
GitHub Issue #1 - Azure Pipelines Bridge Control

Flow:

ChatGPT -> owner-only Issue comment -> GitHub Actions -> Microsoft Entra OIDC -> Azure DevOps REST API -> Azure Pipelines

No PAT is stored.

## GitHub repository variables

Set these repository variables:

- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID

Use the existing Microsoft Entra application/service principal already trusted by the GitHub OIDC configuration.

## Azure DevOps setup

The bridge itself does not need an Azure DevOps Service Connection.

Add the same Microsoft Entra service principal to the Azure DevOps organization and target project.

Recommended initial permissions:

- View build pipeline
- View builds
- Queue builds

Do not grant pipeline edit/delete/admin permissions or repository write/policy-bypass permissions.

Use Basic access for predictable Azure Pipelines access.

## Commands

List pipelines:

/ado-list <org> <project>

Run:

/ado-run <org> <project> <pipelineId> <refs/heads/...>

First production release:

/ado-run <org> <project> <pipelineId> <refs/heads/release/1.0.0> firstProductionRelease=true

Status:

/ado-status <org> <project> <pipelineId> <runId>

Only OWNER comments on Issue #1 are accepted.

## Separate Azure deployment Service Connections

The current Release Pipeline still expects these when it actually deploys or creates a tag:

- sc-cicd-dev
- sc-cicd-uat
- sc-cicd-prod
- sc-cicd-dr
- sc-cicd-tags

These are not needed to prove the Chat-to-Azure-DevOps bridge with /ado-list.
