#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

KUBECONFIG={{kube_config_path}}

kubectl --kubeconfig=${KUBECONFIG} delete node -l type=virtual-kubelet