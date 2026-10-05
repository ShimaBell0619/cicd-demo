targetScope = 'subscription'

@description('Azure region used by the retained validation resources.')
param location string = 'japanwest'

@description('Dedicated resource group for the retained Self-hosted validation.')
param resourceGroupName string = 'rg-cicd-selfhosted-jpw'

@description('Short prefix used for App Service resource names.')
param namePrefix string = 'cicd-sh'

@description('Standard S1 supports the PROD staging slot used by the release PoC.')
@allowed(['S1'])
param skuName string = 'S1'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: { purpose: 'cicd-poc', lifecycle: 'retained', workload: 'selfhosted-validation' }
}

module appService './app-service.bicep' = {
  name: 'app-service'
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
output staging object = appService.outputs.staging
