param location string = resourceGroup().location

// aks
param aksSystemNodePoolVmSize string
param aksSystemNodePoolCount int
param tier string
param kubernetesVersion string
param supportPlan string

// vnet
param aksVnetName string
param aksVnetAddressPrefix string
param aksSubnetAddressPrefix string
param contrainerSubnetAddressPrefix string
param vmssSubnetAddressPrefix string

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
        }
      }
      {
        name: 'vmss'
        properties: {
          addressPrefix: vmssSubnetAddressPrefix
        }
      }
    ]
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
        nodeLabels: {
          'pai-master': 'true'
          'pai-worker': 'false'
        }
        tags: {
          LinuxAzSecPackEnableGIG: 'true'
        }
        // osSKU: 'Ubuntu'
      }
    ])

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
    }

    networkProfile: {
      networkPlugin: 'none'
      dnsServiceIP: '10.0.0.10'
      serviceCidr: '10.0.0.0/16'
    }
    autoUpgradeProfile: null

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

              echo $KUBE_PROXY_UNMANAGED_YAML | base64 -d > kube-proxy-unmanaged.yaml
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
