# cicd-demo

Azure Pipelines CI/CD demo for a Node.js / Next.js App Service workload.

The production target is **Azure Repos Git + Azure Pipelines**. This GitHub repository is only the working mirror used to iterate on the design.

## Delivery model

```text
feature/*
  -> PR / Build Validation
  -> develop
  -> CI
  -> DEV

release/X.Y.Z or hotfix/X.Y.Z
  -> explicit manual Release Pipeline start
  -> Build once
  -> DEV
  -> UAT + human acceptance
  -> Basic merge into main
  -> artifact retention
  -> stale-candidate / current-PROD guard
  -> PROD staging
  -> identity smoke
  -> swap
  -> PROD identity smoke
  -> vX.Y.Z
  -> DR
```

Key properties:

- release/hotfix branch creation does not deploy anything,
- unreviewed PR code and deployment jobs use separate self-hosted hosts/pools,
- DEV/UAT/PROD/DR receive the same immutable ZIP,
- checksums are verified from the downloaded Pipeline Artifact,
- health checks verify the actual commit SHA and Pipeline Build ID,
- UAT is protected against concurrent overwrite while ManualValidation is active,
- a stale release cannot overwrite a newer production hotfix,
- the version tag is created only after production verification,
- successful release artifacts receive a long retention lease,
- PROD Service Connection protection is required in addition to Environment approval.

See:
- [Pipeline implementation](pipelines/README.md)
- [Required Azure DevOps protected-resource controls](docs/azure-devops-controls.md)
