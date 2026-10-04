targetScope = 'resourceGroup'
param location string = 'japanwest'
param vmName string = 'vm-cicd-sh-agent'
param adminUsername string = 'cicdadmin'
@secure()
param adminPassword string

var tags = { purpose: 'cicd-poc', lifecycle: 'retained', workload: 'selfhosted-validation' }

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-cicd-sh-agent'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowSSHFromVirtualNetwork'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'DenyInternetInbound'
        properties: {
          priority: 200
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-cicd-sh'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.74.0.0/16'] }
    subnets: [{ name: 'agents', properties: { addressPrefix: '10.74.1.0/24', networkSecurityGroup: { id: nsg.id }, defaultOutboundAccess: false } }]
  }
}
// Explicit outbound Internet access for Public App Service/ADO; inbound Internet is denied.
resource outboundIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-cicd-sh-agent-egress'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static', publicIPAddressVersion: 'IPv4' }
}
resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: 'nic-cicd-sh-agent'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [{ name: 'primary', properties: { privateIPAllocationMethod: 'Dynamic', subnet: { id: '${vnet.id}/subnets/agents' }, publicIPAddress: { id: outboundIp.id } } }]
  }
}
resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: 'Standard_B2s' }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: 'ubuntu-24_04-lts', sku: 'server', version: 'latest' }
      osDisk: { createOption: 'FromImage', diskSizeGB: 64, managedDisk: { storageAccountType: 'StandardSSD_LRS' } }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      adminPassword: adminPassword
      linuxConfiguration: { disablePasswordAuthentication: false, provisionVMAgent: true }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id }] }
  }
}
resource bastion 'Microsoft.Network/bastionHosts@2024-10-01' = {
  name: 'bas-cicd-sh-developer'
  location: location
  tags: tags
  sku: { name: 'Developer' }
  properties: { virtualNetwork: { id: vnet.id } }
}
output vmId string = vm.id
output registrationPrincipalId string = vm.identity.principalId
output bastionId string = bastion.id
output agentPrivateIp string = nic.properties.ipConfigurations[0].properties.privateIPAddress
