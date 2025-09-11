#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -xe

DEFAULT_RUNTIME="$1"

RUNC_VERSION="1.1.12"
CONTAINERD_VERSION="1.7.15"
CNI_VERSION="v1.5.1"

mkdir -p /etc/containerd
mkdir -p /var/lib/containerd
mkdir -p /opt/cni/bin

curl -o runc -L https://nexusstaticsa.blob.core.windows.net/public/runc/v${RUNC_VERSION}/runc || { echo "Failed to download runc"; exit 1; }
install -m 0555 runc /usr/bin/runc
rm runc

curl -LO https://nexusstaticsa.blob.core.windows.net/public/containerd/v${CONTAINERD_VERSION}/containerd.tar.gz || { echo "Failed to download containerd"; exit 1; }
tar -xvzf containerd.tar.gz -C /usr
rm containerd.tar.gz

curl -LO https://github.com/containernetworking/plugins/releases/download/v1.5.1/cni-plugins-linux-amd64-v1.5.1.tgz || { echo "Failed to download CNI plugins"; exit 1; }
tar -xvzf cni-plugins-linux-amd64-v1.5.1.tgz -C /opt/cni/bin
rm cni-plugins-linux-amd64-v1.5.1.tgz

tee /etc/containerd/config.toml > /dev/null <<EOF
version = 2
oom_score = 0
[plugins."io.containerd.grpc.v1.cri"]
        sandbox_image = "mcr.microsoft.com/oss/kubernetes/pause:3.6"
        [plugins."io.containerd.grpc.v1.cri".containerd]
                default_runtime_name = "$DEFAULT_RUNTIME"
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
                        runtime_type = "io.containerd.runc.v2"
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
                        BinaryName = "/usr/bin/runc"
                        SystemdCgroup = true
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia]
                        privileged_without_host_devices = false
                        runtime_engine = ""
                        runtime_root = ""
                        runtime_type = "io.containerd.runc.v2"
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia.options]
                        BinaryName = "/usr/bin/nvidia-container-runtime"
                        SystemdCgroup = true
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.rocm]
                        privileged_without_host_devices = false
                        runtime_engine = ""
                        runtime_root = ""
                        runtime_type = "io.containerd.runc.v2"
                [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.rocm.options]
                        BinaryName = "/usr/bin/rocm-container-runtime"
                        SystemdCgroup = true
        [plugins."io.containerd.grpc.v1.cri".registry]
                config_path = "/etc/containerd/certs.d"
        [plugins."io.containerd.grpc.v1.cri".registry.headers]
                X-Meta-Source-Client = ["azure/aks"]
[metrics]
        address = "0.0.0.0:10257"
EOF


tee /etc/systemd/system/containerd.service > /dev/null <<EOF
[Unit]
Description=containerd container runtime
Documentation=https://containerd.io
After=network.target local-fs.target
[Service]
ExecStartPre=-/sbin/modprobe overlay
ExecStart=/usr/bin/containerd
Type=notify
Delegate=yes
KillMode=process
Restart=always
RestartSec=5
# Having non-zero Limit*s causes performance problems due to accounting overhead
# in the kernel. We recommend using cgroups to do container-local accounting.
LimitNPROC=infinity
LimitCORE=infinity
LimitNOFILE=infinity
LimitMEMLOCK=infinity
# Comment TasksMax if your systemd version does not supports it.
# Only systemd 226 and above support this version.
TasksMax=infinity
OOMScoreAdjust=-999
[Install]
WantedBy=multi-user.target
EOF

systemctl enable containerd
