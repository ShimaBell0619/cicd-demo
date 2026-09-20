@description('Azure region for the shared App Service Plan and Web Apps.')
param location string

@description('Short resource-name prefix.')
param namePrefix string

@description('App Service Plan SKU. B1 is used for the first low-cost PoC phase.')
param skuName string = 'B1'

var environments = [
  'dev'
  'uat'
  'prod'
  'dr'
]

var uniqueSuffix = uniqueString(resourceGroup().id)
var appServicePlanName = 'asp-${namePrefix}'
var commonTags = {
  purpose: 'cicd-poc'
  lifecycle: 'disposable'
}

resource appServicePlan 'Microsoft.Web/serverfarms@2025-03-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: skuName
    capacity: 1
  }
  properties: {
    reserved: true
    zoneRedundant: false
  }
  tags: commonTags
}

resource webApps 'Microsoft.Web/sites@2025-03-01' = [for environment in environments: {
  name: 'app-${namePrefix}-${environment}-${uniqueSuffix}'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'NODE|22-lts'
      appCommandLine: 'HOSTNAME=0.0.0.0 node server.js'
      alwaysOn: false
      ftpsState: 'Disabled'
      http20Enabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
    }
  }
  tags: union(commonTags, {
    environment: environment
  })
}]

resource appSettings 'Microsoft.Web/sites/config@2025-03-01' = [for (environment, i) in environments: {
  parent: webApps[i]
  name: 'appsettings'
  properties: {
    APP_ENV: environment
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'false'
  }
}]

// Phase 2 intentionally stays out of this first low-cost PoC:
// - upgrade the plan to Standard or Premium
// - add the PROD staging slot
// - add Private Endpoint / Private DNS
// - switch deployment jobs from Microsoft-hosted to self-hosted agents

output appServicePlanName string = appServicePlan.name
output apps array = [for (environment, i) in environments: {
  environment: environment
  name: webApps[i].name
  url: 'https://${webApps[i].properties.defaultHostName}'
}]
