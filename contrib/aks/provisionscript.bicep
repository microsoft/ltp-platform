param hubsub string
param hubgroup string
param extversion string

resource aks 'Microsoft.ContainerService/managedClusters@2024-03-02-preview' existing = {
  name: 'aks-openpai'
  scope: resourceGroup(hubsub, hubgroup)
}

resource aksbootstrapid 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'aksbootstrap'
  scope: resourceGroup(hubsub, hubgroup)
}

var kubeconfig = base64ToString(aks.listClusterUserCredential().kubeconfigs[0].value)

var currentVersion = aks.properties.kubernetesVersion
var currentVersionArray = split(currentVersion, '.')

var kubeletversion = int(currentVersionArray[1]) == 27
  ? '1.27.9' : '1.28.5'

var fqdn = aks.properties.fqdn
var cert = split(substring(kubeconfig, indexOf(kubeconfig, 'certificate-authority-data: ') + 28), '\n')[0]

var waitdnsready = 'echo ${loadFileAsBase64('scripts/waitdnsready.sh')} | base64 -d | bash -s ${fqdn}'
var nvidiadaemonscript = 'echo ${loadFileAsBase64('scripts/nvidiadaemon.sh')} | base64 -d | bash -s'
var nvidiacronjobscript = 'echo ${loadFileAsBase64('scripts/nvidiacronjob.sh')} | base64 -d | bash -s'
var containerdscript = 'echo ${loadFileAsBase64('scripts/containerd.sh')} | base64 -d | bash -s'
var kubeletmsiscript = 'echo ${loadFileAsBase64('scripts/kubelet-msi.sh')} | base64 -d | bash -s ${fqdn} ${aksbootstrapid.properties.clientId}'
var vmssraidsetupscript = 'echo ${loadFileAsBase64('scripts/raidsetup.sh')} | base64 -d | bash'
var kubeletscript = 'echo ${loadFileAsBase64('scripts/kubelet.sh')} | base64 -d | bash -s ${kubeletversion} ${fqdn} ${cert}'

var bootstrapscripts = {
  // Azure SKUs
  Standard_ND96asr_v4: [
    waitdnsready
    vmssraidsetupscript
    nvidiadaemonscript
    '${nvidiacronjobscript} 1215 1410'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96asr_v4 gpu'
  ]

  Standard_ND96amsr_A100_v4: [
    waitdnsready
    vmssraidsetupscript
    nvidiadaemonscript
    '${nvidiacronjobscript} 1593 1410'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96amsr_A100_v4 gpu'
  ]

  Standard_ND96isr_H100_v5: [
    waitdnsready
    vmssraidsetupscript
    nvidiadaemonscript
    '${nvidiacronjobscript} 2619 1980'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96isr_H100_v5 gpu'
  ]

  Standard_E16bs_v5: [
    waitdnsready
    '${containerdscript} runc'
    kubeletmsiscript
    '${kubeletscript} Standard_E16bs_v5 cpu'
  ]

  Standard_D8s_v3: [
    waitdnsready
    '${containerdscript} runc'
    kubeletmsiscript
    '${kubeletscript} Standard_D8s_v3 cpu'
  ]
}

output scripts object = reduce(
  map(items(bootstrapscripts), (entity) => {
    key: entity.key
    val: base64(join(
      concat(
        [
          '#!/bin/bash'
          'set -ex'
          '[[ -f "/var/lib/kubelet/kubeconfig" ]] && echo "please reimage to trigger newer kube ext" && exit 0'
          'echo NEXUS: ${extversion}, HASH ${uniqueString(join(entity.value, '\n'))}'
        ],
        entity.value,
        [
          'shutdown -r +1'
          'echo ${extversion} > /etc/nexus-kube-version'
        ]
      ),
      '\n'
    ))
  }),
  {},
  (cur, next) => union(cur, { '${next.key}': next.val })
)
