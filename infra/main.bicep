targetScope = 'subscription'

@description('Azure region used by the PoC resources.')
param location string = 'japanwest'

@description('Resource group created only for this disposable PoC.')
param resourceGroupName string = 'rg-cicd-demo-poc-jpw'

@description('Short prefix used for App Service resource names.')
param namePrefix string = 'cicd-demo-poc'

@description('Standard S1 supports the PROD staging slot used by the release PoC.')
@allowed(['S1'])
param skuName string = 'S1'

@description('Optional Japan-local expiry date for disposable resources; empty for retained validation.')
param expiresOn string = ''

@allowed(['disposable', 'retained'])
param lifecycle string = 'disposable'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: union({ purpose: 'cicd-poc', lifecycle: lifecycle }, empty(expiresOn) ? {} : { expiresOn: expiresOn })
}

module appService './app-service.bicep' = {
  name: 'app-service-poc'
  scope: resourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    skuName: skuName
    expiresOn: expiresOn
    lifecycle: lifecycle
  }
}

output resourceGroupName string = resourceGroup.name
output appServicePlanName string = appService.outputs.appServicePlanName
output apps array = appService.outputs.apps
output staging object = appService.outputs.staging
