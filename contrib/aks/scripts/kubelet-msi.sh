#!/bin/bash
set -xe

AKS_FQDN=$1
BOOTSTRAP_CLIENT_ID=$2

KUBELOGIN_VERSION="0.0.31"

curl -LO https://nexusstaticsa.blob.core.windows.net/public/kubelogin/v${KUBELOGIN_VERSION}/kubelogin.tar.gz
tar -xvzf kubelogin.tar.gz
mv kubelogin /usr/local/bin
rm kubelogin.tar.gz

mkdir -p /etc/kubernetes

# setup bootstrap kubeconfig
tee /etc/kubernetes/bootstrap-kubeconfig > /dev/null <<EOF
apiVersion: v1
kind: Config
clusters:
- name: localcluster
  cluster:
    certificate-authority: /etc/kubernetes/certs/ca.crt
    server: "https://$AKS_FQDN"
users:
- name: kubelet-bootstrap
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      args:
      - get-token
      - --environment
      - AzurePublicCloud
      - --server-id
      - 6dae42f8-4368-4678-94ff-3960e28e3630 # AKS server application id
      - --login
      - msi
      - --client-id
      - $BOOTSTRAP_CLIENT_ID
      command: kubelogin
      provideClusterInfo: false
contexts:
- context:
    cluster: localcluster
    user: kubelet-bootstrap
  name: bootstrap-context
current-context: bootstrap-context
EOF
