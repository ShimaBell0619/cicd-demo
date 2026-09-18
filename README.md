# cicd-demo

Azure Pipelines CI/CD demo repository.

The first implementation focuses on a **Node.js / Next.js Web App**. The .NET Functions API and batch repositories are expected to follow the same lifecycle later.

The production target is **Azure Repos Git + Azure Pipelines**. This GitHub repository is the working mirror used to develop and review the demo.

## Target lifecycle

```text
feature/*
   |
   | PR / Build Validation
   v
develop -----------------------> CI Pipeline
   |                              Build / SBOM
   |                              |
   |                              v
   |                             DEV
   |
   +--> release/X.Y.Z
   |        |
   |        | manual Run Pipeline
   |        v
   |     Release Pipeline Run
   |        |
   |        +--> Build once
   |        +--> DEV
   |        +--> UAT
   |        +--> pause for UAT acceptance + main merge
   |        +--> verify main / tag vX.Y.Z
   |        +--> PROD approval
   |        +--> PROD staging -> smoke -> swap -> smoke
   |        +--> DR
   |
main <-------------------------- release history
   |
   +--> hotfix/X.Y.Z ----------> same manual Release Pipeline
```

Release/hotfix branch creation does **not** start a deployment. CI continues to validate those branches automatically; a person explicitly starts the Release Pipeline when the branch is ready to become a release candidate.

The release artifact is built once and promoted unchanged through DEV, UAT, PROD, and DR.

## Repository structure

```text
app/                              Minimal Next.js application
pipelines/
  azure-pipelines-ci.yml          CI / PR validation target / DEV deployment
  azure-pipelines-release.yml     Manual release and hotfix promotion pipeline
  templates/
    steps/node-build.yml          npm ci, caches, build, SBOM, package
    stages/deploy-webapp.yml      Reusable App Service deployment stage
    stages/deploy-prod.yml        PROD staging deploy, smoke test, swap
```

See [pipelines/README.md](pipelines/README.md) for the full Azure DevOps setup, Git Flow, permissions, and current tabletop limitation around generating the initial `package-lock.json`.
