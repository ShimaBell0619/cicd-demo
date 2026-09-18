# cicd-demo

Azure Pipelines CI/CD demo repository.

The first implementation focuses on a **Node.js / Next.js Web App**. The .NET Functions API and batch repositories are expected to follow the same release lifecycle later.

## Target lifecycle

```text
feature/*
   |
   | PR
   v
develop -----------------------> CI pipeline
   |                              Build / SBOM
   |                              |
   |                              v
   |                             DEV
   |
   +--> release/X.Y.Z ----------> Release pipeline
   |                              Build once
   |                              |
   |                              +--> DEV
   |                              +--> UAT
   |                              +--> PROD staging
   |                              |      -> smoke test
   |                              |      -> slot swap
   |                              |      -> production smoke test
   |                              +--> DR
   |
main <-------------------------- release history
   |
   +--> hotfix/X.Y.Z ----------> same Release pipeline
```

The release artifact is built once and promoted unchanged through all four environments.

## Repository structure

```text
app/                              Minimal Next.js application
pipelines/
  azure-pipelines-ci.yml          PR/develop CI and DEV deployment
  azure-pipelines-release.yml     release/* and hotfix/* promotion pipeline
  templates/
    steps/node-build.yml          Node install, caches, build, SBOM, package
    stages/deploy-webapp.yml      Reusable App Service deployment stage
    stages/deploy-prod.yml        PROD staging deploy, smoke test, swap
```

See [pipelines/README.md](pipelines/README.md) for the Azure DevOps setup and the intentional first-iteration limitations.
