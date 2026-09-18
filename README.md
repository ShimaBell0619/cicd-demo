# cicd-demo

Azure Pipelines CI/CD design demo for a Node.js / Next.js App Service workload.

The production target is **Azure Repos Git + Azure Pipelines**. GitHub is the working mirror used for design/review.

## v3 lifecycle

```text
feature/*
  -> PR Validation
  -> develop
  -> DEV Pipeline
       Build -> freshness guard -> DEV

release/X.Y.Z | hotfix/X.Y.Z
  -> manual Release Pipeline
       Build once (ephemeral)
       -> DEV
       -> UAT + ManualValidation
       -> exact Basic merge to main
       -> strict release guard
       -> PROD staging
       -> identity smoke
       -> swap
       -> PROD identity smoke
       -> annotated vX.Y.Z
       -> DR

incident / partial failure
  -> manual Recovery Pipeline
       verify-production
       tag-only
       sync-dr
       reverse-swap
       redeploy-production
```

## Security boundaries

- application/package scripts execute only on disposable `build-ephemeral-linux` hosts;
- Git/release control is isolated on `release-control-linux`;
- Azure deployment/private-network access is isolated on `deploy-selfhosted-linux`;
- PR Validation is not authorized to privileged pools/service connections;
- all entry points extend one protected root template;
- release tagging uses a dedicated Azure DevOps service connection backed by Microsoft Entra workload identity, not Project Build Service tag rights;
- PROD deploy, production verification, tag finalization and normal DR synchronization remain in one protected promotion stage.

See:
- [Pipeline behavior](pipelines/README.md)
- [Mandatory Azure DevOps controls and PoC checklist](docs/azure-devops-controls.md)
