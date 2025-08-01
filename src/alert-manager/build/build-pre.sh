#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../kusto-sdk" "../src/node-recycler/kusto-sdk"
cp -arfT "../../kusto-sdk" "../src/node-issue-classifier/kusto-sdk"
cp -arfT "../../kusto-sdk" "../src/alert-parser/kusto-sdk"
cp -arfT "../../kusto-sdk" "../src/job-data-recorder/kusto-sdk"
cp -arfT "../src/node-failure-detection/monitor/data_sources.py" "../src/job-data-recorder/data_sources.py"
cp -arfT "../../database-controller/sdk" "../src/job-status-change-notification/openpaidbsdk"

popd > /dev/null
