# Azure Pipelines setup

This is the Node.js / Next.js tabletop implementation for the delivery model that will later be adapted to .NET Functions.

The production assumption is **Azure Repos Git + Azure Pipelines**. GitHub is only the working mirror used for development/review in this chat.

## Pipeline model

| Pipeline | Trigger | Role |
| --- | --- | --- |
| CI | Automatic on `develop`, `release/*`, `hotfix/*`; PR Build Validation is Branch Policy | Build validation. Only `develop` automatically deploys to shared DEV |
| Release | Manual only | Build once and promote an explicitly selected `release/X.Y.Z` or `hotfix/X.Y.Z` |

Release/hotfix branch creation never starts deployment automatically.

## Current release flow

```text
release/X.Y.Z or hotfix/X.Y.Z
  -> manually start Release Pipeline
  -> Build once
  -> DEV / identity smoke
  -> UAT / identity smoke
  -> ManualValidation while UAT stage remains active
       -> UAT accepted
       -> Basic-merge PR into main
  -> create 10-year retention lease for this run/artifact
  -> PROD protected-resource checks / approval / exclusive lock
  -> release guard:
       branch HEAD == UAT SHA
       exact Basic-merge result tree == UAT candidate tree
       candidate is contained in main
       version tag does not already exist
       candidate contains currently deployed PROD SHA
  -> deploy same ZIP to PROD staging
  -> verify HTTP 200 + expected commit SHA + expected Build ID
  -> swap
  -> verify PROD is running same commit/build
  -> create and remotely verify vX.Y.Z
  -> deploy same artifact to DR
```

The version tag means **production deployment and production identity smoke test succeeded**.

## Normal Git Flow

```text
feature/* -> PR -> develop -> CI -> DEV
develop -> release/X.Y.Z
release fixes -> PR back to develop
release -> UAT -> Basic merge to main -> PROD
```

Any fix made on a release branch must be merged back to `develop` with history preserved so that the current production release SHA remains in future release ancestry.

## Hotfix

A hotfix starts from the **currently deployed production version tag**, not blindly from main HEAD.

```text
currently deployed v1.2.3
  -> hotfix/1.2.4
  -> fix / CI / review
  -> manual Release Pipeline
  -> DEV -> UAT
  -> Basic merge to main
  -> PROD
  -> v1.2.4
  -> DR
  -> Basic-merge hotfix back to develop
  -> also update any active release branch or invalidate/rebuild that release
```

If a hotfix overtakes an older release candidate, reject/cancel the older candidate. It must not resume later.

## Artifact identity

Each run publishes:

```text
webapp.zip
sbom.cdx.json
release-manifest.json
artifact-checksums.sha256
```

Checksums use **relative artifact filenames**, so verification always checks the downloaded Pipeline Artifact rather than a stale build-agent path.

`release-manifest.json` records repository, source SHA, source branch, pipeline definition/run IDs, version, ZIP digest and SBOM digest.

The health endpoint embeds the candidate commit SHA and Pipeline Build ID into the built artifact. Environment smoke tests require:
- HTTP 200,
- `status=ok`,
- expected `commitSha`,
- expected `buildId`.

## Dependencies / cache / SBOM

A committed `package-lock.json` is mandatory and CI uses `npm ci`.

Caches:
- npm download cache keyed by OS, Node and lockfile,
- Next.js incremental cache keyed by OS, architecture, Node, lockfile and source SHA, with broader restore keys,
- no `node_modules` cache.

CycloneDX is pinned as a dev dependency. The generated SBOM is explicitly a **project production-dependency SBOM**, not a claim that it is a byte-for-byte inventory of the final ZIP.

Known tabletop prerequisite: this mirror still needs a valid `package-lock.json` generated from the committed `package.json` in a Node 22 environment:

```bash
npm install --package-lock-only
```

## Production failure / rollback

A production smoke failure after swap does **not** automatically swap back. Automatic rollback is unsafe when data/schema compatibility is unknown.

Use the retained Pipeline Artifact and the runbook in [docs/azure-devops-controls.md](../docs/azure-devops-controls.md). Do not rerun the entire release from Build after a post-swap incident.

## Mandatory Azure DevOps configuration

YAML alone does not enforce the security boundary. Apply every control in [docs/azure-devops-controls.md](../docs/azure-devops-controls.md), particularly:
- physically separate CI / release / deploy agent hosts,
- Exclusive locks,
- PROD Service Connection Approvals and checks,
- Required template from a separately protected template repository,
- Release-only service connection authorization,
- dedicated tag identity,
- Private Endpoint + SCM DNS/reachability.
