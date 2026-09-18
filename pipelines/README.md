# Azure Pipelines setup

This is the first tabletop implementation. It is intentionally small enough to review before the .NET repositories adopt the same lifecycle.

The **production assumption is Azure Repos Git + Azure Pipelines**. This GitHub repository is only a convenient working mirror for developing the demo in chat.

## Pipelines to create

Create two Azure Pipelines against this GitHub repository:

| Pipeline | YAML path | Purpose |
| --- | --- | --- |
| CI | `pipelines/azure-pipelines-ci.yml` | PR validation and automatic DEV deployment from `develop` |
| Release | `pipelines/azure-pipelines-release.yml` | Build once and promote `release/*` / `hotfix/*` through four environments |

## Required Azure DevOps resources

1. An Azure Repos Git repository containing this code.
2. Self-hosted agent pool named `self-hosted-linux`.
3. Azure DevOps Environments: `dev`, `uat`, `prod`, `dr`.
4. Configure a manual approval check on the `prod` Environment.
5. Azure Resource Manager service connections for the target environments.
6. Four Linux App Services. PROD additionally has a `staging` deployment slot.

Replace every `REPLACE_WITH_...` value in the two pipeline entrypoint files.

Approval is intentionally configured on the Azure DevOps Environment rather than in YAML. This keeps the production gate outside the repository-controlled pipeline definition.

## Current Git Flow behavior

### Normal development

```text
feature/* -> PR -> develop
                    |
                    +-> CI build / SBOM
                    +-> automatic DEV deployment
```

### Release

```text
develop
  -> release/1.2.3
       -> Release Pipeline
          -> Build once
          -> DEV
          -> UAT
          -> PROD staging
          -> staging smoke test
          -> slot swap
          -> production smoke test
          -> DR
```

### Hotfix

A hotfix starts from the currently released `main` commit:

```text
main
  -> hotfix/1.2.4
       -> same Release Pipeline
       -> merge back to main and develop after release
```

## Version tagging: first-iteration decision

The release branch name must be exactly `release/X.Y.Z` or `hotfix/X.Y.Z`.

The pipeline extracts `X.Y.Z` and records it in the build number and release manifest.

Creating the immutable Git tag `vX.Y.Z` after UAT acceptance is **not automated yet**. That requires an explicit design for GitHub write credentials and the exact point at which main is updated. We will add it after the basic pipeline lifecycle is reviewed.

## Caching

The build template uses two caches:

- npm's download cache at `$(Pipeline.Workspace)/.npm`
- Next.js incremental build cache at `.next/cache`

It deliberately does not cache `node_modules`.

The repository currently has no committed `package-lock.json`; `npm install` creates it during the build so the demo can be bootstrapped without a local npm execution environment. Before treating this as a production baseline, commit the generated lockfile and switch the install step to `npm ci`. That is the first known hardening item.

## Artifact contents

Each release pipeline run publishes one Pipeline Artifact named `webapp`:

```text
webapp.zip
webapp.zip.sha256
sbom.cdx.json
release-manifest.json
```

All deployments download that same artifact and verify its SHA-256 checksum before deployment.

The Next.js application uses `output: "standalone"`, so `webapp.zip` contains the prebuilt server rather than rebuilding on App Service.

## Smoke tests

The reusable templates support `/api/health` smoke tests.

- DEV/UAT/DR smoke tests are optional in the first iteration because their actual private URLs are not known yet.
- PROD staging and production smoke tests are mandatory. The release entrypoint currently contains `REPLACE_WITH_...` URL placeholders so an unconfigured pipeline fails before a successful production rollout instead of silently skipping verification.

For a Private Endpoint-only App Service, the self-hosted agent must have network/DNS reachability to those endpoints.


## Azure Repos PR validation

Azure Repos Git does not use the YAML `pr:` trigger for pull-request validation.

Configure **Branch Policies > Build validation** on at least `develop` and `main`, pointing to the CI pipeline. Use an automatic, required validation policy for the protected branches.

The YAML therefore explicitly uses `pr: none`; PR validation is an Azure Repos branch-policy concern.

## Manual DEV deployment

The normal path remains automatic:

```text
push/merge to develop
  -> CI pipeline
  -> DEV
```

A manual DEV redeployment is also available without another pipeline: use **Run pipeline**, select the `develop` branch, and run the same CI pipeline. Because the DEV stage is conditioned on `refs/heads/develop`, manually running another branch builds it but does not overwrite the shared DEV environment.

This manual path is intended for retries or deliberate redeployment, not as the default delivery mechanism.
