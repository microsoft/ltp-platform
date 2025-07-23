#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../../dashboard/ltp_productivity.SemanticModel/definition/tables" "../src/tables"

popd > /dev/null
