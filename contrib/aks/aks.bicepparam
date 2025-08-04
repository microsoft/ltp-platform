using './aks.bicep'

// aks
param aksSystemNodePoolVmSize = 'Standard_D8s_v3'
param aksSystemNodePoolCount = 1
param aksPaiMasterNodePoolVmSize = 'Standard_E48as_v4'
param aksPaiMasterNodePoolCount = 1
param tier = 'Standard'
param kubernetesVersion = '1.33.0'
param supportPlan = 'KubernetesOfficial'

// vnet
param aksVnetName = 'openpai-vnet'
param aksVnetNsgName = 'openpai-nsg'
param aksVnetAddressPrefix = '10.16.0.0/16'
param aksSubnetAddressPrefix = '10.16.0.0/23'
param contrainerSubnetAddressPrefix = '10.16.2.0/23'
param vmssSubnetAddressPrefix = '10.16.4.0/23'

// storage
param storageIdentityName = 'pai-storage-identity'
param storageAccountName = 'paistorageaccount'

// managed disk
param prometheusDiskName = 'prometheus-disk'
param prometheusDiskSize = 8192 // 8192 GiB
