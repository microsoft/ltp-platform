using './vmss.bicep'

// scope
param hubsub = ''
param hubgroup = ''

// storage
// this should be the same as in contrib/aks/aks.bicep
param storageIdentityName = 'pai-storage-identity' 

// vmss
param vmssName = 'pai-cpu-vmss'
// this sku should be set into contrib/aks/provisionscript.bicep
param vmssSku = 'Standard_D8s_v3' 
param vmssCount = 1
param adminUsername = 'azureuser'
param imageId = 'hpc'

// vnet
// this should be the vnet of aks set in contrib/aks/aks.bicep
param vnetName = 'openpai-vnet' 
// this should be the nsg of aks set in contrib/aks/aks.bicep
param vnetNsgName = 'openpai-nsg' 

// lb
param lbPublicIpName = 'openpai-lb-public-ip'
param lbName = 'openpai-lb'

// ssh
param sshKeyName = 'openpai-ssh'
