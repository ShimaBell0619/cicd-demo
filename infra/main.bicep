targetScope = 'subscription'

@description('Azure region used by the PoC resources.')
param location string = 'japanwest'

@description('Resource group created only for this disposable PoC.')
param resourceGroupName string = 'rg-cicd-demo-poc-jpw'

@description('Short prefix used for App Service resource names.')
param namePrefix string = 'cicd-demo-poc'

@description('Free App Service Plan SKU for the first PoC phase. F1 intentionally has no deployment slot.')
param skuName string = 'F1'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: {
    purpose: 'cicd-poc'
    lifecycle: 'disposable'
  }
}

module appService './app-service.bicep' = {
  name: 'app-service-poc'
  scope: resourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    skuName: skuName
  }
}

output resourceGroupName string = resourceGroup.name
output appServicePlanName string = appService.outputs.appServicePlanName
output apps array = appService.outputs.apps
