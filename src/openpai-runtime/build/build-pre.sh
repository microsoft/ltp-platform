#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

cp -arfT "../../frameworkcontroller/src" "../src/frameworkcontroller"

popd > /dev/null
