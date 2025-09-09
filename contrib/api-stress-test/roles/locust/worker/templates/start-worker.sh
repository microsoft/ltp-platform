#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

KUBECONFIG={{kube_config_path}}

{% for host in groups['kube-worker'] %}
kubectl --kubeconfig=${KUBECONFIG} label nodes {{ hostvars[host].inventory_hostname }} locust-role=worker
{% endfor %}

kubectl --kubeconfig=${KUBECONFIG} apply -f {{ locust_base_dir }}/worker.yml