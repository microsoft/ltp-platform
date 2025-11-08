#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


pushd $(dirname "$0") > /dev/null

cp -arfT "../../ltp-storage-common" "../src/ltp-storage-common"
cp -arfT "../../kusto-sdk" "../src/kusto-sdk"
cp -arfT "../../postgresql-sdk/sdk" "../src/postgresql-sdk"

popd > /dev/null
