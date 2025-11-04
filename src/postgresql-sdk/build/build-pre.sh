#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../ltp-storage-common/" "../sdk/ltp-storage-common"

popd > /dev/null
