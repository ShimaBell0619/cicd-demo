using './main.bicep'

param location = 'japanwest'
param resourceGroupName = 'rg-cicd-demo-poc-jpw'
param namePrefix = 'cicd-demo-poc'
param skuName = 'S1'
// Set to the Japan-local date of each PoC run; delete the group that same day.
param expiresOn = '2026-10-04'
