# Azure DevOps controls required by the v3 demo

These controls are part of the implementation. YAML alone is not the security boundary.

## Four pipeline definitions

| Pipeline | YAML | Purpose |
| --- | --- | --- |
| PR Validation | `pipelines/azure-pipelines-pr.yml` | Azure Repos Branch Policy validation; release/hotfix branch CI |
| DEV | `pipelines/azure-pipelines-dev.yml` | `develop` build and DEV deployment |
| Release | `pipelines/azure-pipelines-release.yml` | manual Build once promotion |
| Recovery | `pipelines/azure-pipelines-recovery.yml` | manual recovery from retained Release artifacts |

PR Validation must never be authorized to deployment/control pools or Azure deployment service connections.

## Protected root template

Every entry point extends:

`pipelines/templates/pipeline/root.yml`

The working mirror resolves the `policy` repository resource from `cicd-demo@main`. Required Template checks must point to the same protected ref.

For production, move the **root plus every privileged child stage/step template it calls** to a dedicated Azure Repos policy repository and pin an approved protected ref/tag. Do not keep the root protected while privileged child scripts come back from `@self`.

The root exposes only typed mode/ID parameters. It intentionally exposes no arbitrary `stepList`, pool, service-connection, or script injection parameter.

## Agent trust boundaries

Use separate hosts. Pool separation on the same VM is insufficient.

| Pool | Workload | Trust boundary |
| --- | --- | --- |
| `build-ephemeral-linux` | PR validation, DEV build, Release build | Executes application/package scripts. Recreate/discard after every job. No PE, deploy, tag, or privileged Managed Identity access |
| `release-control-linux` | Git guard, retention, recovery control | Never runs application build/test scripts. Repo read and Azure DevOps control only |
| `deploy-selfhosted-linux` | App Service deploy and health checks | ARM/Entra/Azure DevOps outbound plus App/SCM Private Endpoint access. Never executes PR/application build scripts |

Required utilities:
- build: Node 22/npm and archive tooling;
- control: git, jq, curl, Azure CLI;
- deploy: jq, curl and Azure Pipelines task prerequisites.

## Agent-pool Pipeline permissions and checks

Disable Open access.

- `build-ephemeral-linux`: authorize PR Validation, DEV, Release.
- `release-control-linux`: authorize Release and Recovery only.
- `deploy-selfhosted-linux`: authorize DEV, Release and Recovery only.
- PR Validation must not appear in control/deploy pool permissions.

Agent pools are protected resources. Apply Required Template checks to privileged pools. Use Branch control where applicable and require protected branches.

The intended branch contract is:
- DEV privileged access: protected `refs/heads/develop`;
- Release: protected `release/*` or `hotfix/*`;
- Recovery: protected `refs/heads/main`.

A YAML condition is not the security boundary.

## Service connections

Use workload identity federation.

For DEV/UAT/PROD/DR ARM service connections:
- disable "Grant access permission to all pipelines";
- authorize only required Pipeline definitions;
- scope Azure RBAC narrowly;
- configure Branch control and Required Template checks.

PROD additionally requires:
- production approvers;
- self-approval disabled;
- Exclusive lock;
- Release and Recovery Pipeline authorization only.

## Dedicated Azure DevOps tag identity

Do **not** grant Create tag to Project Build Service.

Create an **Azure DevOps service connection backed by a dedicated Microsoft Entra workload identity**. Grant that identity only the repository permissions required to read/create immutable release tags. Authorize that service connection only for Release and Recovery.

The implementation uses `AzureCLI@3` with `connectionType: azureDevOps` and the Azure DevOps REST Annotated Tags API. Application Build jobs never receive this identity.

Verify effective permissions deny:
- ordinary branch writes;
- Force push;
- protected-tag deletion/update;
- policy bypass.

## Environments and Exclusive lock

Create:
- `dev`
- `uat`
- `prod`
- `dr`

Enable Exclusive lock and use `lockBehavior: sequential`.

UAT Deploy + ManualValidation stay in one stage, preserving UAT exclusivity during human testing.

Normal PROD deploy, PROD tag creation, production retention and DR synchronization are deliberately one stage. PROD/DR protected-resource locks therefore cover the successful production identity and tag finalization, preventing the previous "PROD success -> lock release -> tag later" race.

If a hotfix overtakes a pending candidate, cancel/reject that candidate. Never resume it later.

## Git-flow contract

### DEV

Only current remote `develop` HEAD may deploy. A delayed older DEV run fails its freshness guard.

### Release / Hotfix

After UAT:

1. Basic-merge the exact UAT `Build.SourceVersion` into `main`.
2. At promotion time, `main HEAD` must still be that exact two-parent merge commit.
3. The second parent must equal the UAT candidate SHA.
4. The main HEAD tree must equal the UAT candidate tree.
5. Current PROD SHA must be an ancestor of the candidate.

Any later main commit, revert or hotfix invalidates the candidate. Refresh the release branch from current main, rebuild and repeat UAT.

The release source branch may be deleted after merge; branch existence is not used as proof.

## Version/tag contract

`vX.Y.Z` means:

> this immutable Release Run artifact successfully passed PROD post-swap identity verification.

The annotated tag message includes:
- Release Pipeline Run ID;
- webapp ZIP SHA-256.

If PROD succeeds but tag creation fails, normal promotion of the same version is rejected because PROD itself reports that version. Use Recovery `tag-only` with the original Release Run ID.

A tag is historical release evidence, not the current-deployment pointer after rollback.

## Runtime environment identity

Set runtime App Setting `APP_ENV`:

| Target | Value |
| --- | --- |
| DEV | `dev` |
| UAT | `uat` |
| PROD production slot | `prod` |
| PROD staging slot | `prod-staging` |
| DR | `dr` |

For PROD, mark `APP_ENV` as a deployment-slot setting so the values stay with their slots across swap.

Health returns environment + artifact version + commit SHA + Release Build ID. Smoke tests parse top-level JSON with `jq` and poll until the exact identity appears.

## Build once

Keep App Service build-on-deploy disabled.

Environment differences must be runtime configuration. Do not bake environment-specific `NEXT_PUBLIC_*` or other statically evaluated environment values into the common artifact.

Define slot-setting behavior for secrets, connections and environment-specific endpoints.

Native dependencies require build-host/App Service OS, CPU and libc compatibility.

## Private Endpoint / SCM

The deployment host needs DNS + TCP/443 to both application and SCM/Kudu endpoints.

PROD staging has its own slot Private Endpoint/private DNS records.

Also permit required outbound access to ARM, Entra ID, Azure DevOps and Pipeline Artifact endpoints.

## Artifact verification

`artifact-checksums.sha256` is required to contain exactly:
- `webapp.zip`
- `sbom.cdx.json`
- `release-manifest.json`

The verifier rejects unexpected checksum entries and absolute/parent-relative paths, verifies all hashes, parses the manifest as JSON, and independently compares ZIP/SBOM digests.

This protects integrity inside the trusted Pipeline Artifact channel; it is not a standalone cryptographic provenance signature.

## Retention

- UAT-accepted candidate: 30-day lease.
- Successfully tagged production Release Run: 3650-day lease.

Choose real retention from audit/RTO/RPO requirements during implementation.

## Recovery Pipeline

Never recover by rebuilding or rerunning normal promotion.

Recovery is manual from protected `main` and accepts explicit Release Pipeline Run IDs.

Actions:
- `verify-production`: show current PROD health identity;
- `tag-only`: prove a retained Release Run is exactly what PROD is running, then create only its missing tag;
- `sync-dr`: prove the selected retained artifact is current PROD before copying it to DR;
- `reverse-swap`: prove both PROD and staging identities correspond to explicit retained runs before reverse swap;
- `redeploy-production`: deploy an explicit retained rollback artifact through staging and swap when the old staging content cannot be trusted.

Rollback does not rewrite main or historical tags automatically.

DB/schema compatibility is a human recovery prerequisite.

## PoC validation checklist

The isolated Azure DevOps PoC should prove:

1. PR Validation cannot use control/deploy pools.
2. A feature branch cannot queue a privileged definition and bypass Required Template/Branch control.
3. Release Build host is discarded before a control/tag job runs.
4. Project Build Service cannot create tags.
5. Dedicated Azure DevOps service connection can create a tag but cannot push branches/delete protected tags.
6. UAT lock is held during ManualValidation.
7. PROD lock remains through production smoke, tag and normal DR attempt.
8. App/SCM Private DNS and TCP/443 work for production and staging.
9. A stale Release is rejected after a newer hotfix/main change.
10. Tag failure is recovered with tag-only, without redeploying.
11. An old failed DR Run cannot overwrite DR after a newer production release.
12. reverse-swap and retained-artifact redeploy behave as documented.
