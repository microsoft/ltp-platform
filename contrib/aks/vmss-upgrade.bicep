param hubsub string = ''
param hubgroup string = ''

resource vmss 'Microsoft.Compute/virtualMachineScaleSets@2023-03-01' existing = {
  name: 'openpai-vmss'
}

module vmextscript 'provisionscript.bicep' = {
  name: 'kube'
  params: {
    extversion: '000000'
    hubgroup: hubgroup
    hubsub: hubsub
  }
}

resource vmssExt 'Microsoft.Compute/virtualMachineScaleSets/extensions@2021-04-01' = {
  name: 'kube-000000'
  parent: vmss
  properties: {
    publisher: 'Microsoft.Azure.Extensions'
    type: 'CustomScript'
    typeHandlerVersion: '2.1'
    protectedSettings: {
      script: vmextscript.outputs.scripts[vmss.sku.name]
    }
  }
}
