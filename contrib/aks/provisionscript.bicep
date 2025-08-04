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

var kubeletversion = aks.properties.kubernetesVersion

var fqdn = aks.properties.fqdn
var cert = split(substring(kubeconfig, indexOf(kubeconfig, 'certificate-authority-data: ') + 28), '\n')[0]

var waitdnsready = 'echo ${loadFileAsBase64('scripts/waitdnsready.sh')} | base64 -d | bash -s ${fqdn}'
var nvidiadaemonscript = 'echo ${loadFileAsBase64('scripts/nvidiadaemon.sh')} | base64 -d | bash -s'
var nvidiacronjobscript = 'echo ${loadFileAsBase64('scripts/nvidiacronjob.sh')} | base64 -d | bash -s'
var nvidianvswitch = 'echo ${loadFileAsBase64('scripts/nvidianvswitch.sh')} | base64 -d | bash -s'
var containerdscript = 'echo ${loadFileAsBase64('scripts/containerd.sh')} | base64 -d | bash -s'
var kubeletmsiscript = 'echo ${loadFileAsBase64('scripts/kubelet-msi.sh')} | base64 -d | bash -s ${fqdn} ${aksbootstrapid.properties.clientId}'
var vmssraidsetupscript = 'echo ${loadFileAsBase64('scripts/raidsetup.sh')} | base64 -d | bash'
var kubeletscript = 'echo ${loadFileAsBase64('scripts/kubelet.sh')} | base64 -d | bash -s ${kubeletversion} ${fqdn} ${cert}'
var tlsscanscript = 'echo ${loadFileAsBase64('scripts/update-tls-scan.sh')} | base64 -d | bash -s'
var blobproxyscript = 'echo ${loadFileAsBase64('scripts/enable-blob-proxy.sh')} | base64 -d | bash -s'
var configipoibscript = 'echo ${loadFileAsBase64('scripts/config-ipoib.sh')} | base64 -d | bash -s'
var rocmruntimescript = 'echo ${loadFileAsBase64('scripts/rocm-runtime.sh')} | base64 -d | bash -s'
var installfusescript = 'echo ${loadFileAsBase64('scripts/install-fuse.sh')} | base64 -d | bash -s'
var installamdgpudriverscript = 'echo ${loadFileAsBase64('scripts/enable-amd-gpu.sh')} | base64 -d | bash -s'

var bootstrapscripts = {
  // Azure SKUs
  Standard_ND96asr_v4: [
    waitdnsready
    installfusescript
    vmssraidsetupscript
    nvidiadaemonscript
    '${nvidiacronjobscript} 1215 1410'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96asr_v4 gpu'
    tlsscanscript
    blobproxyscript
  ]

  Standard_ND96amsr_A100_v4: [
    waitdnsready
    installfusescript
    vmssraidsetupscript
    nvidiadaemonscript
    '${nvidiacronjobscript} 1593 1410'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96amsr_A100_v4 gpu'
    tlsscanscript
    blobproxyscript
  ]

  Standard_ND96isr_MI300X_v5: [
    waitdnsready
    installamdgpudriverscript
    installfusescript
    vmssraidsetupscript
    rocmruntimescript
    '${containerdscript} rocm'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96isr_MI300X_v5 gpu'
    tlsscanscript
    blobproxyscript
    configipoibscript
  ]

  Standard_ND96isr_H100_v5: [
    waitdnsready
    installfusescript
    vmssraidsetupscript
    '${nvidianvswitch} 2619 1980'
    '${containerdscript} nvidia'
    kubeletmsiscript
    '${kubeletscript} Standard_ND96isr_H100_v5 gpu'
    tlsscanscript
    blobproxyscript
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

  Standard_E8ds_v4: [
    waitdnsready
    '${containerdscript} runc'
    kubeletmsiscript
    '${kubeletscript} Standard_E8ds_v4 cpu'
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
