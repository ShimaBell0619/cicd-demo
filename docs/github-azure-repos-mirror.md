# GitHub to Azure Repos mirror

GitHub is the source of truth for the PoC repository.

Azure Repos is a one-way execution mirror used by Azure Pipelines.

## Repository

Azure Repos:

https://dev.azure.com/shimaoka0619/cicd-demo/_git/cicd-demo

Organization: shimaoka0619  
Project: cicd-demo  
Repository: cicd-demo

## Workflow

`.github/workflows/mirror-azure-repos.yml`

The workflow mirrors:

- `main`
- `develop`
- `release/**`
- `hotfix/**`
- `v*` tags

It never force-pushes. If Azure Repos contains divergent commits, synchronization fails instead of overwriting them.

Branch and tag deletion is intentionally not mirrored in this PoC.

## Authentication

GitHub Actions -> GitHub OIDC -> Microsoft Entra service principal -> Azure DevOps access token -> Azure Repos Git

No PAT is stored.

GitHub repository variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

## Azure DevOps permissions

Add the same Microsoft Entra service principal used by GitHub OIDC to the Azure DevOps organization/project.

Repository permissions required for mirroring:

- Read
- Contribute
- Create branch
- Create tag

Do not grant:

- Force push
- Manage permissions
- Bypass policies when completing pull requests
- Bypass policies when pushing

For the Chat-to-Pipelines bridge, the same identity also needs the Pipeline permissions documented in `docs/chat-azure-pipelines-bridge.md`.

## Operating rule

Do not make normal code changes directly in Azure Repos.

GitHub is the source of truth. Azure Repos receives mirrored commits and tags.

Strict PR-required Branch Policy on a mirrored branch can block the mirror by design, so Branch Policy behavior is validated separately from the mirror mechanism.
