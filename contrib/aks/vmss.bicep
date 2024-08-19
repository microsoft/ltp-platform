param location string = resourceGroup().location

// vmss
param vmssSku string
param vmssCount int
param vmssName string = '${replace(replace(vmssSku, 'Standard_', ''), '_', '')}-${uniqueString(resourceGroup().id)}'
param adminUsername string
param imageId string

// vnet
param vnetName string
param vnetNsgName string

// lb
param lbPublicIpName string
param lbName string

// ssh
param sshKeyName string

// scope
param hubsub string
param hubgroup string

resource aksBootstrapUai 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'aksbootstrap'
  scope: resourceGroup(hubsub, hubgroup)
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' existing = {
  name: vnetName
  scope: resourceGroup(hubsub, hubgroup)
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: vnetNsgName
  location: location
}

resource lbPubIp 'Microsoft.Network/publicIPAddresses@2021-08-01' = {
  name: lbPublicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAddressVersion: 'IPv4'
    publicIPAllocationMethod: 'Static'
  }
}

resource lb 'Microsoft.Network/loadBalancers@2023-11-01' = {
  name: lbName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    frontendIPConfigurations: [
      {
        name: 'frontend-config'
        properties: {
          publicIPAddress: {
            id: lbPubIp.id
          }
        }
      }
    ]
    outboundRules: [
      {
        name: 'outbound-rule'
        properties: {
          backendAddressPool: {
            id: resourceId('Microsoft.Network/loadBalancers/backendAddressPools', lbName, 'backend-pool')
          }
          enableTcpReset: true
          frontendIPConfigurations: [
            {
              id: resourceId('Microsoft.Network/loadBalancers/frontendIPConfigurations', lbName, 'frontend-config')
            }
          ]
          idleTimeoutInMinutes: 5
          protocol: 'All'
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'backend-pool'
      }
    ]
    inboundNatPools: [
      {
        name: 'ssh-nat-pool'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/loadBalancers/frontendIPConfigurations', lbName, 'frontend-config')
          }
          protocol: 'tcp'
          frontendPortRangeStart: 50000
          frontendPortRangeEnd: 50999
          backendPort: 22
        }
      }
    ]
  }
}

resource sshKey 'Microsoft.Compute/sshPublicKeys@2023-09-01' existing = {
  name: sshKeyName
  scope: resourceGroup(hubsub, hubgroup)
}

resource vmss 'Microsoft.Compute/virtualMachineScaleSets@2023-03-01' = {
  name: vmssName
  location: location
  tags: {
    AzSecPackAutoConfigReady: 'true'
    LinuxAzSecPackEnableGIG: 'true'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${aksBootstrapUai.id}': {}
    }
  }
  sku: {
    name: vmssSku
    tier: 'Standard'
    capacity: vmssCount
  }
  properties: {
    overprovision: false
    singlePlacementGroup: true
    orchestrationMode: 'Uniform'
    upgradePolicy: {
      mode: 'Manual'
    }
    platformFaultDomainCount: 1
    virtualMachineProfile: {
      storageProfile: {
        imageReference: imageId == 'ubuntu'
          ? {
              publisher: 'Canonical'
              offer: '0001-com-ubuntu-server-jammy'
              sku: '22_04-lts-gen2'
              version: 'latest'
            }
          : {
              publisher: 'microsoft-dsvm'
              offer: 'ubuntu-hpc'
              sku: '2204'
              version: 'latest'
            }
        osDisk: {
          createOption: 'FromImage'
          caching: 'ReadWrite'
          diskSizeGB: 512
          managedDisk: {
            storageAccountType: 'Premium_LRS'
          }
        }
        diskControllerType: 'SCSI'
      }
      extensionProfile: {
        extensions: [
          {
            name: 'kube-000000'
            properties: {
              publisher: 'Microsoft.Azure.Extensions'
              type: 'CustomScript'
              typeHandlerVersion: '2.1'
              protectedSettings: {
                script: vmextScript.outputs.scripts[vmssSku]
              }
            }
          }
        ]
      }
      osProfile: {
        computerNamePrefix: '${vmssName}-'
        adminUsername: adminUsername
        linuxConfiguration: {
          disablePasswordAuthentication: true
          ssh: {
            publicKeys: [
              {
                path: '/home/${adminUsername}/.ssh/authorized_keys'
                keyData: sshKey.properties.publicKey
              }
            ]
          }
        }
      }
      networkProfile: {
        networkInterfaceConfigurations: [
          {
            name: '${vmssName}-nic'
            properties: {
              primary: true
              enableAcceleratedNetworking: false
              disableTcpStateTracking: false
              enableIPForwarding: false
              networkSecurityGroup: {
                id: nsg.id
              }
              ipConfigurations: [
                {
                  name: '${vmssName}-ip'
                  properties: {
                    subnet: {
                      id: first(filter(vnet.properties.subnets, s => s.name == 'vmss'))!.id
                    }
                    primary: true
                    loadBalancerBackendAddressPools: [
                      {
                        id: lb.properties.backendAddressPools[0].id
                      }
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    }
  }
}

module vmextScript './provisionscript.bicep' = {
  name: 'kube'
  params: {
    extversion: '000000'
    hubgroup: hubgroup
    hubsub: hubsub
  }
}
