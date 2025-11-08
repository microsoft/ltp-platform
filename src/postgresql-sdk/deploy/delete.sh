#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

echo "Deleting PostgreSQL SDK Service resources..."

# Delete sync job if it exists
kubectl delete job postgresql-sdk-sync --ignore-not-found=true

popd > /dev/null
