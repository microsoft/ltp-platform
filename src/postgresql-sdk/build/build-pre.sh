#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../ltp-common/data_schema" "../sdk/ltp_postgresql_sdk/data_schema"

popd > /dev/null
