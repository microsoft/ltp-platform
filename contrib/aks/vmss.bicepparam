using './vmss.bicep'

// scope
param hubsub = ''
param hubgroup = ''

// vmss
param vmssSku = 'Standard_D8s_v3'
param vmssCount = 1
param adminUsername = 'azureuser'
param imageId = 'hpc'

// vnet
param vnetName = 'openpai-vnet'
param vnetNsgName = 'openpai-nsg'

// lb
param lbPublicIpName = 'openpai-lb-public-ip'
param lbName = 'openpai-lb'

// ssh
param sshKeyName = 'openpai-ssh'
