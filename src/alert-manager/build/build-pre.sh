#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

# Copy ltp-storage-common (shared data schemas, interfaces, and factory)
cp -arfT "../../ltp-storage-common" "../src/node-recycler/ltp-storage-common"
cp -arfT "../../ltp-storage-common" "../src/node-issue-classifier/ltp-storage-common"
cp -arfT "../../ltp-storage-common" "../src/alert-parser/ltp-storage-common"
cp -arfT "../../ltp-storage-common" "../src/job-data-recorder/ltp-storage-common"

# Copy SDKs (backend implementations)
cp -arfT "../../kusto-sdk" "../src/node-recycler/kusto-sdk"
cp -arfT "../../postgresql-sdk/sdk" "../src/node-recycler/postgresql-sdk"
cp -arfT "../../kusto-sdk" "../src/node-issue-classifier/kusto-sdk"
cp -arfT "../../postgresql-sdk/sdk" "../src/node-issue-classifier/postgresql-sdk"
cp -arfT "../../kusto-sdk" "../src/alert-parser/kusto-sdk"
cp -arfT "../../postgresql-sdk/sdk" "../src/alert-parser/postgresql-sdk"
cp -arfT "../../kusto-sdk" "../src/job-data-recorder/kusto-sdk"
cp -arfT "../../postgresql-sdk/sdk" "../src/job-data-recorder/postgresql-sdk"

# Copy other dependencies
cp -arfT "../src/node-failure-detection/monitor/data_sources.py" "../src/job-data-recorder/data_sources.py"
cp -arfT "../../database-controller/sdk" "../src/job-status-change-notification/openpaidbsdk"

popd > /dev/null
