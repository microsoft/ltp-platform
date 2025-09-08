#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

KUBECONFIG={{kube_config_path}}

kubectl --kubeconfig=${KUBECONFIG} create configmap locust-script-configuration --from-file={{ locust_base_dir }}/configmap/ --dry-run=client -o yaml | kubectl --kubeconfig=${KUBECONFIG} apply --overwrite=true -f - || exit $?

kubectl --kubeconfig=${KUBECONFIG} apply -f {{ locust_base_dir }}/locust-sa.yml