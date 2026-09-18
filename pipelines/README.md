# Azure Pipelines setup

This repository is a tabletop implementation of the Node.js / Next.js delivery model before the .NET repositories adopt the same lifecycle.

The **production assumption is Azure Repos Git + Azure Pipelines**. This GitHub repository is only a working mirror used while developing the demo in chat.

## Pipeline model

Create two Azure Pipelines:

| Pipeline | YAML path | Trigger | Purpose |
| --- | --- | --- | --- |
| CI | `pipelines/azure-pipelines-ci.yml` | Automatic on `develop`, `release/*`, `hotfix/*`; Branch Policy for PRs | Build validation and automatic DEV deployment from `develop` |
| Release | `pipelines/azure-pipelines-release.yml` | **Manual only** | Build once and promote an explicitly selected `release/*` or `hotfix/*` branch |

The release pipeline is deliberately not triggered by branch creation or push. Creating `release/1.2.3` or `hotfix/1.2.4` means "work on this release"; manually queuing the Release Pipeline means "promote this branch as a release candidate."

## Required Azure DevOps resources

1. Azure Repos Git repository containing this code.
2. Self-hosted Linux agent pool named `self-hosted-linux`.
3. Azure DevOps Environments: `dev`, `uat`, `prod`, `dr`.
4. Manual Approval check configured on the `prod` Environment.
5. Azure Resource Manager service connections for each target environment.
6. Four Linux App Services; PROD additionally has a `staging` deployment slot.
7. The project Build Service identity must be able to read the repo and create Git tags. The pipeline uses `checkout: persistCredentials: true` only in the release-finalization job.

Replace every `REPLACE_WITH_...` value before attempting an Azure deployment.

## Git Flow

### Feature development

```text
feature/*
  -> local development
  -> PR to develop
  -> Branch Policy Build Validation
  -> review
  -> merge to develop
  -> CI Pipeline
  -> DEV
```

Feature branches do not automatically deploy to the shared DEV environment. A developer can manually run the CI Pipeline against a feature branch to validate the build, but the DEV deployment stage is guarded so that only `develop` deploys there.

### Normal release

```text
develop
  -> release/1.2.3
  -> fixes / CI until ready
  -> prepare and review PR to main
  -> manually Run Release Pipeline on release/1.2.3
       -> Build once
       -> DEV
       -> UAT
       -> pause
       -> accept UAT
       -> complete release/1.2.3 -> main PR using Basic merge
       -> resume same Pipeline Run
       -> verify release SHA is contained in main
       -> create tag v1.2.3 on that exact SHA
       -> PROD Environment approval
       -> PROD staging
       -> staging smoke test
       -> slot swap
       -> production smoke test
       -> DR
```

### Hotfix

```text
main
  -> hotfix/1.2.4
  -> implement fix
  -> CI
  -> PR to main + review + Build Validation
  -> manually Run the same Release Pipeline on hotfix/1.2.4
       -> Build once
       -> DEV
       -> UAT
       -> pause
       -> complete PR to main using Basic merge
       -> resume
       -> create v1.2.4 on the exact hotfix SHA
       -> PROD approval
       -> PROD
       -> DR
  -> after release, merge the fix back into develop through a PR
```

The normal release and hotfix use the same Release Pipeline. Their main differences are the source branch and the post-release need to bring a hotfix back into `develop`.

## Why Basic merge is required for main

The UAT-tested artifact is tied to `Build.SourceVersion`. The Release Pipeline checks that this exact source commit is an ancestor of `origin/main` before tagging.

A squash or rebase merge creates different commit identities. Configure the `main` branch policy to allow the release/hotfix process to use **Basic merge (no fast-forward)** so the tested source SHA remains in main history.

## Azure Repos PR validation

Azure Repos Git does not support YAML PR triggers. Configure **Branch Policies > Build validation** on at least:

- `develop`: required CI validation before feature integration.
- `main`: required CI validation before release/hotfix integration.

PR review requirements, minimum reviewers, comment resolution, and allowed merge types should also be configured as branch policies rather than encoded in YAML.

## Manual Release Pipeline start

The Release Pipeline uses:

```yaml
trigger: none
pr: none
```

Start it from **Run pipeline**, explicitly select `release/X.Y.Z` or `hotfix/X.Y.Z`, and run it. The first stage rejects any other branch or malformed version.

Branch names intentionally omit the `v` prefix:

- branch: `release/1.2.3`
- branch: `hotfix/1.2.4`
- immutable version tag: `v1.2.3`, `v1.2.4`

## One Release Pipeline Run

A single queued Release Pipeline Run owns the immutable artifact and remains the same run through the whole promotion:

```text
Build
 -> DEV
 -> UAT
 -> ManualValidation (UAT accepted + main PR merged)
 -> main ancestry verification
 -> vX.Y.Z tag
 -> PROD Environment Approval
 -> PROD staging / smoke / swap / smoke
 -> DR
```

The `ManualValidation@1` job is agentless and pauses the existing run rather than starting another pipeline.

## Production approval

Production approval is intentionally configured as an **Approvals and checks** rule on the Azure DevOps `prod` Environment, not inside repository YAML. Repository contributors therefore cannot remove the production gate by editing the pipeline file alone.

## Manual DEV redeployment

Normal behavior:

```text
merge/push to develop -> CI -> DEV
```

For a retry or deliberate redeployment, manually run the CI Pipeline and select `develop`. Running the CI Pipeline manually against another branch performs the build but does not deploy that branch to shared DEV.

## Dependency reproducibility and cache

A committed `package-lock.json` is mandatory. The build fails immediately when it is missing.

The template uses:

- `npm ci` for deterministic dependency installation.
- npm download cache: `$(Pipeline.Workspace)/.npm`.
- Next.js incremental cache: `.next/cache`.
- no `node_modules` cache.

`@cyclonedx/cyclonedx-npm` is a pinned dev dependency so SBOM generation does not download an arbitrary tool version during the build.

**Current tabletop limitation:** this working mirror does not yet contain `package-lock.json`. The current execution environment cannot reach the npm registry, so a valid lockfile was not fabricated. Generate it once from this committed `package.json` in a Node 22 environment, review it, and commit it before the first CI execution:

```bash
npm install --package-lock-only
```

After that, CI uses only `npm ci`.

## Artifact contents

Each Release Pipeline Run publishes one Pipeline Artifact named `webapp`:

```text
webapp.zip
webapp.zip.sha256
sbom.cdx.json
release-manifest.json
```

DEV, UAT, PROD, and DR download that same artifact and verify its SHA-256 checksum before deployment. No environment rebuild occurs.

The Next.js application uses `output: "standalone"`, so `webapp.zip` contains the prebuilt server.

## Smoke tests and Private Endpoint

The reusable templates support `/api/health`.

- DEV/UAT/DR smoke-test URLs are optional until their real private names are defined.
- PROD staging and production smoke tests are mandatory and use explicit placeholders so an unconfigured release cannot silently swap.

For Private Endpoint-only App Service, the self-hosted agent must have routing and DNS resolution to the production and staging private endpoints.

## Tag permissions

The finalization job uses `persistCredentials: true` so Git commands can reuse the Azure Pipelines OAuth credential. Grant the project Build Service identity only the repository permissions needed for this action, especially **Read** and **Create tag**. Do not grant branch-policy bypass for this design.

The tag job is idempotent: if `vX.Y.Z` already exists on the expected source SHA, it succeeds; if the tag exists on a different SHA, it fails.
