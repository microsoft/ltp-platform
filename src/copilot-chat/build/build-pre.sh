#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../../docs/LuciaTrainingPlatform/manual/user" "../src/copilot_agent/data/LTP/manual/user"

popd > /dev/null
