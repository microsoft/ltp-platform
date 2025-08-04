#!/bin/bash

pushd $(dirname "$0") > /dev/null

kubectl apply --overwrite=true -f copilot-chat.yaml || exit $?

# Wait until the service is ready.
PYTHONPATH="../../../deployment" python -m k8sPaiLibrary.monitorTool.check_pod_ready_status -w -k app -v copilot-chat || exit $?

popd > /dev/null