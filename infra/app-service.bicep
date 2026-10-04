@description('Azure region for the shared App Service Plan and Web Apps.')
param location string

@description('Short resource-name prefix.')
param namePrefix string

@description('Standard S1 is shared by the four apps and PROD staging for this disposable PoC.')
@allowed(['S1'])
param skuName string = 'S1'

@description('Delete all PoC resources on this Japan-local calendar date.')
param expiresOn string

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
  expiresOn: expiresOn
}

var runtimeConfig = {
  linuxFxVersion: 'NODE|22-lts'
  appCommandLine: 'HOSTNAME=0.0.0.0 node server.js'
  alwaysOn: true
  ftpsState: 'Disabled'
  http20Enabled: true
  minTlsVersion: '1.2'
  scmMinTlsVersion: '1.2'
  healthCheckPath: '/api/health'
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
    siteConfig: runtimeConfig
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
    ENABLE_ORYX_BUILD: 'false'
    WEBSITE_SWAP_WARMUP_PING_PATH: '/api/health'
    WEBSITE_SWAP_WARMUP_PING_STATUSES: '200'
  }
}]

resource stagingSlot 'Microsoft.Web/sites/slots@2025-03-01' = {
  parent: webApps[2]
  name: 'staging'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: runtimeConfig
  }
  tags: union(commonTags, { environment: 'prod-staging' })
}

resource stagingSettings 'Microsoft.Web/sites/slots/config@2025-03-01' = {
  parent: stagingSlot
  name: 'appsettings'
  properties: {
    APP_ENV: 'prod-staging'
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'false'
    ENABLE_ORYX_BUILD: 'false'
    WEBSITE_SWAP_WARMUP_PING_PATH: '/api/health'
    WEBSITE_SWAP_WARMUP_PING_STATUSES: '200'
  }
}

// APP_ENV identifies the physical slot and must stay fixed across swaps.
resource prodSlotConfig 'Microsoft.Web/sites/config@2025-03-01' = {
  parent: webApps[2]
  name: 'slotConfigNames'
  properties: {
    appSettingNames: ['APP_ENV']
    connectionStringNames: []
    azureStorageConfigNames: []
  }
}

output appServicePlanName string = appServicePlan.name
output apps array = [for (environment, i) in environments: {
  environment: environment
  name: webApps[i].name
  url: 'https://${webApps[i].properties.defaultHostName}'
}]

output staging object = {
  name: stagingSlot.name
  app: webApps[2].name
  url: 'https://${stagingSlot.properties.defaultHostName}'
}
