#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -e

echo "pai" > cluster-id

# assume the workdir is pai
echo "Generating services configurations..."
python3 ./contrib/kubespray/script/openpai_generator.py -l ./contrib/kubespray/config/layout.yaml -c ./contrib/kubespray/config/config.yaml -o /cluster-configuration

echo "Pushing cluster config to k8s..."
./paictl.py config push -p /cluster-configuration -m service < cluster-id

echo "Starting OpenPAI service..."
./paictl.py service start -n cluster-configuration device-plugin node-exporter job-exporter openpai-runtime \
  log-manager prometheus grafana alert-manager watchdog internal-storage postgresql frameworkcontroller database-controller \
  hivedscheduler rest-server webportal pylon < cluster-id

rm cluster-id
