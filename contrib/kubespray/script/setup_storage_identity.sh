#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -e
if [ $# -lt 2 ]; then
  echo "Usage: $0 <resourceGroup> <storageIndentityName>"
  exit 1
fi
resourceGroup="$1"
storageIndentityName="$2"

echo "Get client ID of the storage identity..."
storageIdentityId=$(az identity show --name "$storageIndentityName" --resource-group "$resourceGroup" --query "clientId" -o tsv)
if [ -z "$storageIdentityId" ]; then
  echo "Error: Failed to get client ID for storage identity '$storageIndentityName' in resource group '$resourceGroup'."
  exit 1
fi

issueUrl=$(az aks show --name aks-openpai --resource-group "$resourceGroup" --query "oidcIssuerProfile.issuerUrl" --output tsv)

if [ -z "$issueUrl" ]; then
  echo "Error: Failed to get OIDC issuer URL for AKS cluster."
  exit 1
fi

echo "Creating service account 'blob-access-pod-sa' in namespace 'default'..."
kubectl create serviceaccount blob-access-pod-sa -n default

echo "Creating federated credential for the service account..."
az identity federated-credential create \
  --name blob-access-pod-federated-cred \
  --identity-name "$storageIndentityName" \
  --resource-group "$resourceGroup" \
  --issuer "$issueUrl" \
  --subject system:serviceaccount:default:blob-access-pod-sa

echo "Creating configmap 'blob-access-pod-identity' in namespace 'default' with storageIdentityId..."
kubectl create configmap blob-access-pod-identity -n default --from-literal=storageIdentityId="$storageIdentityId"
