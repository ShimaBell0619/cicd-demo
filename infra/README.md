# Disposable S1 CI/CD PoC

This PoC uses Japan West and deletes its Azure resources on the day of the test.

## Resources

- One disposable resource group: `rg-cicd-demo-poc-jpw`.
- One Linux Standard S1 App Service Plan, shared by DEV/UAT/PROD/DR and PROD staging.
- Four Web Apps and the PROD `staging` deployment slot.
- Public App/SCM endpoints, HTTPS, TLS 1.2, Node.js 22, build-on-deploy disabled.
- `APP_ENV` is fixed to each environment. PROD marks it as a slot setting.
- No Private Endpoint, Private DNS or self-hosted agent is provisioned.

DR here verifies artifact distribution and is on the same plan/region. It does not validate regional disaster recovery.

## Bootstrap

Set `expiresOn` in `poc.bicepparam` to today's date in Japan, then validate and preview:

```bash
az bicep build --file infra/main.bicep
az deployment sub validate --location japanwest --name cicd-demo-poc --template-file infra/main.bicep --parameters infra/poc.bicepparam
az deployment sub what-if --location japanwest --name cicd-demo-poc --template-file infra/main.bicep --parameters infra/poc.bicepparam
az deployment sub create --location japanwest --name cicd-demo-poc --template-file infra/main.bicep --parameters infra/poc.bicepparam
```

The subscription bootstrap creates the group. After configuring `sc-cicd-infra` with Contributor on this group only, run `pipelines/infra.yml` manually. It validates, previews and reconciles `app-service.bicep`, and publishes the generated names/URLs as the `infra` artifact. It refuses a group without today's disposable PoC tags. Update the Release variables from the deployment outputs.

## Release

Use `pipelines/release.yml` with Microsoft-hosted `ubuntu-24.04` deployment jobs. The production self-hosted pool remains commented beside each deployment job. Keep human UAT validation and the PROD service-connection approval enabled. This disposable single-user PoC permits approval by the initiating user; restore the documented production setting before real use.

## Same-day cleanup

After recording Run IDs, artifact identity and results, delete the entire PoC group. This also deletes managed identities placed inside the group, their federated credentials and their resource-scoped Azure permissions. Remove their temporary Azure DevOps membership and service connections separately.

```bash
az group show --name rg-cicd-demo-poc-jpw --query tags
az group delete --name rg-cicd-demo-poc-jpw --yes
az group exists --name rg-cicd-demo-poc-jpw
```

The last command must return `false`. An expiry tag alone does not delete resources. Do not fall back to leaving an idle S1 plan or downgrading to F1; delete the resources that same day.

## Previous phase

On 2026-09-20 the F1 four-app bootstrap succeeded in Japan West and was deleted. This S1 phase adds PROD staging to validate deploy, smoke, swap, tag and DR. Private networking was explicitly excluded from this test.
