#!/bin/bash
set -xe

KUBE_VERSION=$1
AKS_FQDN=$2
KUBE_CA_CERT=$3
INSTANCE_TYPE=$4
PROCESSOR_TYPE=$5

NODE_NAME=$(hostname)

mkdir -p /var/lib/cni
mkdir -p /opt/cni/bin
mkdir -p /etc/cni/net.d
mkdir -p /etc/kubernetes/volumeplugins
mkdir -p /etc/kubernetes/certs
mkdir -p /etc/systemd/system/kubelet.service.d
mkdir -p /var/lib/kubelet


KUBELET_CA="/etc/kubernetes/certs/ca.crt"
touch "${KUBELET_CA}"
chmod 0600 "${KUBELET_CA}"
chown root:root "${KUBELET_CA}"
echo $KUBE_CA_CERT | base64 -d > /etc/kubernetes/certs/ca.crt

KUBELET_SERVER_PRIVATE_KEY_PATH="/etc/kubernetes/certs/kubeletserver.key"
KUBELET_SERVER_CERT_PATH="/etc/kubernetes/certs/kubeletserver.crt"
openssl genrsa -out $KUBELET_SERVER_PRIVATE_KEY_PATH 4096
openssl req -new -x509 -days 7300 -key $KUBELET_SERVER_PRIVATE_KEY_PATH -out $KUBELET_SERVER_CERT_PATH -subj "/CN=system:node:${NODE_NAME}"

curl -LO https://nexusstaticsa.blob.core.windows.net/public/k8s/v${KUBE_VERSION}/kubernetes-node-linux-amd64.tar.gz
tar -xvzf kubernetes-node-linux-amd64.tar.gz kubernetes/node/bin/kubelet
mv kubernetes/node/bin/kubelet /usr/local/bin
rm kubernetes-node-linux-amd64.tar.gz

# setup wicred
mkdir -p /opt/image-cred-provider/config/
mkdir -p /opt/image-cred-provider/bin/

touch /opt/image-cred-provider/bin/workload-identity-token

tee /opt/image-cred-provider/config/workload-identity-token.yaml > /dev/null <<EOF
kind: CredentialProviderConfig
apiVersion: kubelet.config.k8s.io/v1
providers:
- name: workload-identity-token
  apiVersion: credentialprovider.kubelet.k8s.io/v1
  matchImages:
  - "*.azurecr.io"
  args:
  - /var/run/workload-identity-token.sock
  defaultCacheDuration: 1m
EOF
# end setup wicred

# adust flags as desired
tee /etc/default/kubelet > /dev/null <<EOF
KUBELET_NODE_LABELS="kubernetes.azure.com/mode=system,kubernetes.azure.com/role=agent,node.kubernetes.io/exclude-from-external-load-balancers=true,kubernetes.azure.com/managed=false,kubernetes.io/os=linux,node.kubernetes.io/instance-type=$INSTANCE_TYPE,RepairStatus=Validate"
KUBELET_FLAGS="--address=0.0.0.0 --anonymous-auth=false --authentication-token-webhook=true --authorization-mode=Webhook --cgroup-driver=systemd --cgroups-per-qos=true --client-ca-file=/etc/kubernetes/certs/ca.crt --cluster-dns=10.0.0.10 --cluster-domain=cluster.local --enforce-node-allocatable=pods --event-qps=0 --eviction-hard=memory.available<500Mi,nodefs.available<50Gi,imagefs.available<200Gi,nodefs.inodesFree<5% --image-gc-high-threshold=99 --image-gc-low-threshold=90 --keep-terminated-pod-volumes=false --kube-reserved=cpu=180m,memory=3399Mi,pid=1000 --kubeconfig=/var/lib/kubelet/kubeconfig --max-pods=110 --node-status-update-frequency=10s --pod-infra-container-image=mcr.microsoft.com/oss/kubernetes/pause:3.6 --protect-kernel-defaults=true --read-only-port=0 --rotate-certificates=true --streaming-connection-idle-timeout=4h --tls-cert-file=/etc/kubernetes/certs/kubeletserver.crt --tls-cipher-suites=TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,TLS_RSA_WITH_AES_256_GCM_SHA384,TLS_RSA_WITH_AES_128_GCM_SHA256 --tls-private-key-file=/etc/kubernetes/certs/kubeletserver.key --image-credential-provider-config=/opt/image-cred-provider/config/workload-identity-token.yaml --image-credential-provider-bin-dir=/opt/image-cred-provider/bin --container-log-max-size=5Gi --container-log-max-files=2"
EOF

# can simplify this + 2 following files by merging together
tee /etc/systemd/system/kubelet.service.d/10-containerd.conf > /dev/null <<'EOF'
[Service]
Environment=KUBELET_CONTAINERD_FLAGS="--runtime-request-timeout=15m --container-runtime-endpoint=unix:///run/containerd/containerd.sock"
EOF

tee /etc/systemd/system/kubelet.service.d/10-tlsbootstrap.conf > /dev/null <<'EOF'
[Service]
Environment=KUBELET_TLS_BOOTSTRAP_FLAGS="--kubeconfig /var/lib/kubelet/kubeconfig --bootstrap-kubeconfig /etc/kubernetes/bootstrap-kubeconfig"
EOF

tee /etc/systemd/system/kubelet.service > /dev/null <<'EOF'
[Unit]
Description=Kubelet
ConditionPathExists=/usr/local/bin/kubelet
Requires=containerd.service
After=containerd.service
[Service]
Restart=always
EnvironmentFile=/etc/default/kubelet
SuccessExitStatus=143
# Ace does not recall why this is done
ExecStartPre=/bin/bash -c "if [ $(mount | grep \"/var/lib/kubelet\" | wc -l) -le 0 ] ; then /bin/mount --bind /var/lib/kubelet /var/lib/kubelet ; fi"
TimeoutSec=1200
ExecStartPre=/bin/mount --make-shared /var/lib/kubelet
ExecStartPre=-/sbin/ebtables -t nat --list
ExecStartPre=-/sbin/iptables -t nat --numeric --list
ExecStart=/usr/local/bin/kubelet \
        --enable-server \
        --node-labels="${KUBELET_NODE_LABELS}" \
        --v=2 \
        --volume-plugin-dir=/etc/kubernetes/volumeplugins \
        $KUBELET_TLS_BOOTSTRAP_FLAGS \
        $KUBELET_CONFIG_FILE_FLAGS \
        $KUBELET_CONTAINERD_FLAGS \
        $KUBELET_FLAGS
[Install]
WantedBy=multi-user.target
EOF

tee /etc/sysctl.d/999-sysctl-aks.conf > /dev/null <<EOF
# container networking
net.ipv4.ip_forward = 1
net.ipv4.conf.all.forwarding = 1
net.ipv6.conf.all.forwarding = 1
net.bridge.bridge-nf-call-iptables = 1

# refer to https://github.com/kubernetes/kubernetes/blob/75d45bdfc9eeda15fb550e00da662c12d7d37985/pkg/kubelet/cm/container_manager_linux.go#L359-L397
vm.overcommit_memory = 1
kernel.panic = 10
kernel.panic_on_oops = 1
# to ensure node stability, we set this to the PID_MAX_LIMIT on 64-bit systems: refer to https://kubernetes.io/docs/concepts/policy/pid-limiting/
kernel.pid_max = 4194304
# https://github.com/Azure/AKS/issues/772
fs.inotify.max_user_watches = 1048576
# Ubuntu 22.04 has inotify_max_user_instances set to 128, where as Ubuntu 18.04 had 1024.
fs.inotify.max_user_instances = 1024

# This is a partial workaround to this upstream Kubernetes issue:
# https://github.com/kubernetes/kubernetes/issues/41916#issuecomment-312428731
net.ipv4.tcp_retries2=8
net.core.message_burst=80
net.core.message_cost=40
net.core.somaxconn=16384
net.ipv4.tcp_max_syn_backlog=16384
net.ipv4.neigh.default.gc_thresh1=4096
net.ipv4.neigh.default.gc_thresh2=8192
net.ipv4.neigh.default.gc_thresh3=16384
EOF
sysctl --system


systemctl enable kubelet

if [[ /etc/rsyslog.d/50-default.conf ]]
then
    if ! grep kubelet /etc/rsyslog.d/50-default.conf
    then
        echo "if \$programname == 'kubelet' then /var/log/kubelet.log" >> /etc/rsyslog.d/50-default.conf
		systemctl restart rsyslog
    fi
fi
