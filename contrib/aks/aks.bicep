param location string = resourceGroup().location

// aks
param aksSystemNodePoolVmSize string
param aksSystemNodePoolCount int
param aksPaiMasterNodePoolVmSize string
param aksPaiMasterNodePoolCount int
param tier string
param kubernetesVersion string
param supportPlan string

// vnet
param aksVnetName string
param aksVnetNsgName string
param aksVnetAddressPrefix string
param aksSubnetAddressPrefix string
param contrainerSubnetAddressPrefix string
param vmssSubnetAddressPrefix string

// storage
param storageIdentityName string
param storageAccountName string

param storageAccountSku string = 'Standard_GRS'
param storageAccountKind string = 'StorageV2'

// managed disk
param prometheusDiskName string
param prometheusDiskSize int

// UAI for AKS
resource aksUai 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  location: location
  name: 'aks'
}

// assign contributor role to the UAI for AKS
resource aksUaiRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aksUai.id, 'contributor')
  properties: {
    description: 'Assign aksUai contributor role on the resource group' // default scope
    principalId: aksUai.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b24988ac-6180-42a0-ab88-20f7382dd24c'
    ) // contributor
  }
}

// UAI for ACR
resource aksAcrUai 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  location: location
  name: 'aksacr'
}

// network security group for AKS
resource aksNsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: aksVnetNsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowCorpSSHInbound'
        properties: {
          priority: 1000
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefixes: [
            '131.107.0.0/16'
            '167.220.0.0/16'
          ]
          destinationPortRange: '22'
          destinationAddressPrefix: '*'
          access: 'Allow'
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowCorpWebInbound'
        properties: {
          priority: 1001
          protocol: '*'
          sourcePortRange: '*'
          sourceAddressPrefixes: [
            '131.107.0.0/16'
            '167.220.0.0/16'
          ]
          destinationPortRanges: [
            '80'
            '443'
          ]
          destinationAddressPrefix: '*'
          access: 'Allow'
          direction: 'Inbound'
        }
      }
    ]
  }
}

// network for AKS
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: aksVnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        aksVnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'AKS'
        properties: {
          addressPrefix: aksSubnetAddressPrefix
          networkSecurityGroup: {
            id: aksNsg.id
          }
        }
      }
      {
        name: 'ContainerInstance'
        properties: {
          addressPrefix: contrainerSubnetAddressPrefix
          delegations: [
            {
              name: 'aciDelegation'
              properties: {
                serviceName: 'Microsoft.ContainerInstance/containerGroups'
              }
            }
          ]
          networkSecurityGroup: {
            id: aksNsg.id
          }
        }
      }
      {
        name: 'vmss'
        properties: {
          addressPrefix: vmssSubnetAddressPrefix
          networkSecurityGroup: {
            id: aksNsg.id
          }
        }
      }
    ]
  }
}

// create a managed identity for storage
resource storageIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  location: location
  name: storageIdentityName
}

// create a storage account for AKS as PV
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: storageAccountKind
  sku: {
    name: storageAccountSku
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${storageIdentity.id}': {}
    }
  }
  properties: {
    allowSharedKeyAccess: false
  }
}

// Assign Storage Blob Data Owner role to the storage identity
resource storageIdentityRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageIdentity.id, 'Storage Blob Data Owner')
  scope: storageAccount
  properties: {
    description: 'Assign Storage Blob Data Owner role to the storage identity'
    principalId: storageIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b7e6dc6d-f1e8-4753-8033-0f276bb0955b' // Storage Blob Data Owner
    )
  }
}

resource storageIdentityBlobDataReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageIdentity.id, 'Storage Blob Data Reader')
  scope: storageAccount
  properties: {
    description: 'Assign Storage Blob Data Reader role to the storage identity'
    principalId: storageIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
    )
  }
}

resource storageIdentityBlobDataContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageIdentity.id, 'Storage Blob Data Contributor')
  scope: storageAccount
  properties: {
    description: 'Assign Storage Blob Data Contributor role to the storage identity'
    principalId: storageIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    )
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  name: 'default'
  parent: storageAccount
}

resource userLogsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'user-logs'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

resource prometheusContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'prometheus'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// AKS
resource aks 'Microsoft.ContainerService/managedClusters@2024-03-02-preview' = {
  name: 'aks-openpai'
  location: location
  dependsOn: [
    aksUaiRa
  ]
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${aksUai.id}': {}
    }
  }
  sku: {
    name: 'Base'
    tier: tier
  }
  properties: {
    dnsPrefix: 'aks-openpai'
    kubernetesVersion: kubernetesVersion
    agentPoolProfiles: concat([
      {
        name: 'sysnodepool'
        vnetSubnetID: '${vnet.id}/subnets/AKS'
        enableAutoScaling: false
        mode: 'System'
        osType: 'Linux'
        count: aksSystemNodePoolCount
        vmSize: aksSystemNodePoolVmSize
        tags: {
          LinuxAzSecPackEnableGIG: 'true'
        }
        identity: {
          type: 'UserAssigned'
          userAssignedIdentities: {
            '${storageIdentity.id}': {}
          }
        }
        // osSKU: 'Ubuntu'
      }
      {
        name: 'paimaster'
        vnetSubnetID: '${vnet.id}/subnets/AKS'
        enableAutoScaling: false
        mode: 'User'
        osType: 'Linux'
        count: aksPaiMasterNodePoolCount
        vmSize: aksPaiMasterNodePoolVmSize
        nodeLabels: {
          'pai-master': 'true'
        }
        tags: {
          LinuxAzSecPackEnableGIG: 'true'
        }
        identity: {
          type: 'UserAssigned'
          userAssignedIdentities: {
            '${storageIdentity.id}': {}
          }
        }
      }
    ])

    storageProfile: {
      blobCSIDriver: {
        enabled: true
      }
    }

    disableLocalAccounts: false

    supportPlan: supportPlan
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }

    oidcIssuerProfile: {
      enabled: true
    }

    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
      imageCleaner: {
        enabled: true
        intervalHours: 48
      }
    }

    identityProfile: {
      kubeletidentity: {
        resourceId: aksAcrUai.id
      }
      storageidentity: {
        resourceId: storageIdentity.id
      }
    }

    networkProfile: {
      networkPlugin: 'none'
      dnsServiceIP: '10.0.0.10'
      serviceCidr: '10.0.0.0/16'
    }

    autoUpgradeProfile: {
      upgradeChannel: 'patch'
    }

    addonProfiles: {
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: {
          enableSecretRotation: 'true'
          rotationPollInterval: '2m'
        }
      }
    }
  }
}

// UAI for AKS Bootstrap
resource aksBootstrapUai 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  location: location
  name: 'aksbootstrap'
}

// assign bootstrap role to aksBootstrapUai
resource configAks 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: 'configaks'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${aksUai.id}': {}
    }
  }
  properties: {
    subnetIds: [
      {
        id: '${vnet.id}/subnets/ContainerInstance'
      }
    ]
    containers: [
      {
        name: 'configaks'
        properties: {
          image: 'mcr.microsoft.com/azure-cli:2.41.0'
          command: [
            'sh'
            '-c'
            'echo $INIT_SCRIPT | base64 -d | dos2unix | bash'
          ]
          resources: {
            requests: {
              cpu: 1
              memoryInGB: 1
            }
          }
          environmentVariables: [
            {
              name: 'AKS_VERSION'
              value: aks.properties.kubernetesVersion
            }
            {
              name: 'INIT_SCRIPT'
              value: base64('''
              set -xe
              az login -i
              az aks install-cli

              az aks get-credentials --resource-group $RESOURCEGROUP --name aks-openpai -a

              echo $BOOTSTRAP_ROLE_YAML | base64 -d > nodebootstrap.yaml
              sed -i "s|__OBJECT_ID__|${BOOTSTRAP_MSI}|g" ./nodebootstrap.yaml
              kubectl apply -f ./nodebootstrap.yaml

              echo $CILIUM_YAML | base64 -d > cni.yaml
              kubectl apply -f ./cni.yaml

              echo $KUBE_PROXY_UNMANAGED_YAML | base64 -d > kube-proxy-unmanaged.yaml]
              sed -i "s|__KUBE_VERSION__|${AKS_VERSION}|g" ./kube-proxy-unmanaged.yaml
              kubectl apply -f ./kube-proxy-unmanaged.yaml

              echo $WI_IMAGE_CRED_PROVIDER_YAML | base64 -d > wi-image-cred-provider.yaml
              sed -i "s|__CLIENT_ID__|${ACR_CLIENT_ID}|g" ./wi-image-cred-provider.yaml
              kubectl apply -f ./wi-image-cred-provider.yaml

              az aks update -g $RESOURCEGROUP -n aks-openpai --disable-local-accounts
              az container delete -g $RESOURCEGROUP -n configaks -y
              ''')
            }
            {
              name: 'RESOURCEGROUP'
              value: resourceGroup().name
            }
            {
              name: 'LOCATION'
              value: location
            }
            {
              name: 'BOOTSTRAP_MSI'
              value: aksBootstrapUai.properties.principalId
            }
            {
              name: 'BOOTSTRAP_CLIENTID'
              value: aksBootstrapUai.properties.clientId
            }
            {
              name: 'BOOTSTRAP_ROLE_YAML'
              value: loadFileAsBase64('k8s-deploy/bootstrap-role.yaml')
            }
            {
              name: 'CILIUM_YAML'
              value: loadFileAsBase64('k8s-deploy/cilium.yaml')
            }
            {
              name: 'KUBE_PROXY_UNMANAGED_YAML'
              value: loadFileAsBase64('k8s-deploy/kube-proxy-unmanaged.yaml')
            }
            {
              name: 'ACR_CLIENT_ID'
              value: aksAcrUai.properties.clientId
            }
            {
              name: 'WI_IMAGE_CRED_PROVIDER_YAML'
              value: loadFileAsBase64('k8s-deploy/wi-image-cred-provider.yaml')
            }
          ]
        }
      }
    ]
    restartPolicy: 'Never'
    osType: 'Linux'
  }
}

// add federated identity credential to the "aksacr" UAI
resource federatedCrendial 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: aksAcrUai
  name: 'aksacrfc'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:kube-system:azure-acr-identity'
  }
}

param userID string = az.deployer().objectId

// assign the user as "Azure Kubernetes Service RBAC Cluster Admin" to the aks
resource aksClusterAdminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aks.id, userID, 'Azure Kubernetes Service RBAC Cluster Admin')
  scope: aks
  properties: {
    description: 'Assign aksClusterAdminRoleAssignment role to the user'
    principalId: userID
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b'
    ) // Azure Kubernetes Service RBAC Cluster Admin
  }
}

resource prometheusManagedDisk 'Microsoft.Compute/disks@2025-01-02' = {
  name: prometheusDiskName
  location: location
  properties: {
    diskSizeGB: prometheusDiskSize
    creationData: {
      createOption: 'Empty'
    }
    networkAccessPolicy: 'AllowAll'
    publicNetworkAccess: 'Enabled'
  }
  sku: {
    name: 'Premium_LRS'
  }
}
