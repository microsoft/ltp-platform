#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

KUBECONFIG={{kube_config_path}}


kubectl --kubeconfig=${KUBECONFIG} label nodes {{ hostvars[groups['kube-master'][0]].inventory_hostname }} locust-role=master

kubectl --kubeconfig=${KUBECONFIG} apply -f {{ locust_base_dir }}/master.yml