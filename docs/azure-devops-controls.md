# Azure DevOps controls required by this demo

The YAML cannot create or enforce all Azure DevOps protected-resource controls. Treat the settings below as part of the implementation, not optional documentation.

## Agent trust boundaries

Use separate hosts, not merely separate agent registrations on the same VM.

| Pool | Workload | Azure / private-network access |
| --- | --- | --- |
| `ci-selfhosted-linux` | PR Build Validation, develop/release/hotfix CI | No production service connections; no App Service Private Endpoint route; preferably ephemeral |
| `release-selfhosted-linux` | manually started trusted release build, Git/read/tag control jobs | Repository access only; no App Service deployment credential |
| `deploy-selfhosted-linux` | DEV/UAT/PROD/DR deployments and smoke tests | Required Azure service connections and private DNS/routes |

PR code must never run on the deployment host.

## Environments and exclusive locks

Create `dev`, `uat`, `prod`, and `dr` Environments.

Enable **Exclusive lock** on all shared deployment environments. YAML uses `lockBehavior: sequential`.

The UAT deployment and ManualValidation are intentionally inside one stage so the UAT stage remains active while a human tests the candidate. Only one candidate may occupy UAT at a time.

If a hotfix must overtake an older release candidate, reject/cancel the older UAT run first. Do not let it resume later.

## Production service connection

Do not rely only on the `prod` Environment approval.

For the PROD Azure Resource Manager service connection:

1. Disable "Grant access permission to all pipelines".
2. Authorize only the Release Pipeline.
3. Configure **Approvals and checks** on the service connection itself.
4. Configure a **Required template** check for the production release policy. The demo Release Pipeline now uses `extends` with `pipelines/templates/pipeline/release.yml`, so the check has an explicit root policy template to require.
5. For production, move that policy template to a separately protected Azure Repos template repository/ref that release branches cannot modify, and point both `extends` and the Required template check at that protected template.

The in-repository policy template demonstrates the enforcement shape, but it is not a strong security boundary while a release branch can modify the same repository.

The `prod` Environment should also have:
- designated production approvers,
- self-approval disabled,
- Exclusive lock.

## UAT ManualValidation

Replace `REPLACE_WITH_UAT_APPROVERS` with a group such as `[Project]\UAT Approvers`.

The task:
- notifies only that group,
- only that group can resume/reject,
- does not allow the run requester to approve their own run,
- times out and rejects after six days.

## Git permissions

`main` and `develop` must use Branch Policies.

For `main` release/hotfix PRs:
- require review and Build Validation,
- allow/require Basic merge for this workflow,
- do not grant branch-policy bypass to pipelines.

Tagging needs a distinct trusted identity in production. Azure Pipelines job tokens are normally scoped to a Project Build Service identity, not a single job. For a strong boundary, run the Release Pipeline/tagging job from a dedicated release Azure DevOps project (or equivalent dedicated identity) that is not available to PR validation.

Grant the tagging identity only the repository rights it needs, including Read and Create tag. Do not grant Force push or policy bypass.

## Private Endpoint / SCM reachability

The deployment agent needs DNS and TCP/443 reachability for both application and SCM/Kudu endpoints.

For each private App Service verify:
- application FQDN,
- SCM FQDN,
- Azure Resource Manager / Entra ID / Azure DevOps outbound dependencies.

PROD staging uses its own Private Endpoint; it is not shared with the production slot. Ensure the slot-specific private DNS records are present.

## App Service runtime contract

Build-on-deploy must remain disabled. The ZIP already contains the Next.js standalone server.

Environment differences must be runtime configuration. Do not bake environment-specific `NEXT_PUBLIC_*` values into a Build-once artifact.

Define and review which App Settings / connection strings are slot settings before using swap. Secrets and environment-specific backend endpoints should remain with their intended slot.

## Retention

The Release Pipeline creates a 3650-day retention lease immediately after UAT acceptance and before production deployment. The System.AccessToken identity therefore needs permission to create build retention leases.

This keeps the accepted Pipeline Run and its Pipeline Artifact available for rollback/audit beyond ordinary project retention.

## Rollback policy

No unconditional automatic rollback is performed.

After a production swap:
- if production smoke succeeds, tag the exact candidate SHA and continue to DR;
- if production smoke fails, keep the PROD exclusive lock context operationally frozen and determine actual slot state before changing anything;
- if the previous version remains in staging and application/data changes are backward compatible, reverse-swap is the fastest rollback;
- otherwise redeploy the previously retained immutable artifact.

Database/schema changes must be backward compatible with both versions before relying on slot rollback.

Never rerun the whole Release Pipeline to recover a post-swap failure. Retry the failed deployment/recovery action against the known artifact after checking actual slot state.
