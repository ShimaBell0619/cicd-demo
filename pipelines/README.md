# Azure Pipelines v3

Production target: **Azure Repos Git + Azure Pipelines**.

## Four Pipeline definitions

| Pipeline | YAML | Start |
| --- | --- | --- |
| PR Validation | `azure-pipelines-pr.yml` | Azure Repos Branch Policy; release/hotfix push CI |
| DEV | `azure-pipelines-dev.yml` | automatic `develop` |
| Release | `azure-pipelines-release.yml` | manual `release/X.Y.Z` or `hotfix/X.Y.Z` |
| Recovery | `azure-pipelines-recovery.yml` | manual protected `main` |

All entry points extend one protected root policy template.

## Normal development

```text
feature/*
  -> PR Validation
  -> develop
  -> DEV Pipeline
       Build on ephemeral host
       -> reject stale develop Run
       -> deploy DEV
       -> verify env/SHA/Build ID
```

## Release

```text
release/X.Y.Z or hotfix/X.Y.Z
  -> manual Release Pipeline
  -> Build once on disposable build host
  -> DEV
  -> UAT
  -> ManualValidation
       UAT accepted
       exact candidate Basic-merged to main
  -> 30-day candidate retention
  -> protected PROD/DR promotion stage
       read current PROD identity
       strict main HEAD/candidate/current-PROD guard
       deploy same ZIP to staging
       wait for exact staging identity
       swap
       wait for exact PROD identity
       create annotated vX.Y.Z using dedicated Entra WIF Azure DevOps identity
       create long production retention lease
       deploy same tagged artifact to DR
       verify exact DR identity
```

`vX.Y.Z` is created before the PROD/DR promotion stage releases its protected-resource lock.

Any main change after UAT merge invalidates the candidate.

## Recovery

Do not rerun normal Release after a post-swap incident.

Recovery actions:
- `verify-production`
- `tag-only`
- `sync-dr`
- `reverse-swap`
- `redeploy-production`

Recovery downloads a **specific Release Pipeline Run** using `DownloadPipelineArtifact@2`. It operates on the retained artifact rather than rebuilding from Git.

## Artifact

```text
webapp.zip
sbom.cdx.json
release-manifest.json
artifact-checksums.sha256
```

Manifest identifies source commit, source branch, Pipeline definition/Run, artifact version, ZIP digest, SBOM digest and SBOM scope.

Smoke tests also validate runtime `APP_ENV`, preventing a correct artifact on the wrong environment/slot URL from passing.

## Known prerequisite

Generate and commit a valid Node 22 `package-lock.json` before the first execution:

```bash
npm install --package-lock-only
```

Pipeline installs use `npm ci` thereafter.

See [docs/azure-devops-controls.md](../docs/azure-devops-controls.md) before creating the Azure DevOps resources.
