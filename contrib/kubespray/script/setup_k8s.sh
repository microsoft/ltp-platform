#!/bin/bash
set -e

script_path=$(dirname "$(readlink -f "$0")")
echo "Script path: $script_path"
# install blob csi driver, whcih is in this repo: https://github.com/kubernetes-sigs/blob-csi-driver
csi_driver_config_file="https://raw.githubusercontent.com/kubernetes-sigs/blob-csi-driver/refs/heads/master/deploy/csi-blob-driver.yaml"
csi_node_config_url="https://raw.githubusercontent.com/kubernetes-sigs/blob-csi-driver/refs/heads/master/deploy/csi-blob-node.yaml"

csi_node_config_file="$script_path/csi-blob-node-tmp.yaml"
python $script_path/modify_csi_blob_node_yaml.py $csi_node_config_url $csi_node_config_file

echo "Installing CSI driver..."
kubectl apply -f $csi_node_config_file
kubectl apply -f $csi_driver_config_file

# create pvc and pv in the k8s cluster
pvc_config_file="$script_path/../aks-pvc.yaml"
pv_config_file="$script_path/../aks-pv.yaml"
if [ ! -f "$pvc_config_file" ]; then
  echo "PVC config file not found: $pvc_config_file"
  exit 1
fi
if [ ! -f "$pv_config_file" ]; then
  echo "PV config file not found: $pv_config_file"
  exit 1
fi
echo "Creating PVC and PV..."
kubectl apply -f $pv_config_file
kubectl apply -f $pvc_config_file

