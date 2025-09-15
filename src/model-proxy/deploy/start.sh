#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

kubectl apply --overwrite=true -f model-proxy.yaml || exit $?

# Wait until the service is ready.
PYTHONPATH="../../../deployment" python -m  k8sPaiLibrary.monitorTool.check_pod_ready_status -w -k app -v model-proxy || exit $?

popd > /dev/null
