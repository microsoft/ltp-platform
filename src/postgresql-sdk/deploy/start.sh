#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

pushd $(dirname "$0") > /dev/null

echo "Starting PostgreSQL SDK Service..."

# Delete old sync job if exists
kubectl delete job postgresql-sdk-sync --ignore-not-found=true

# Apply Job template
kubectl apply -f postgresql-sdk-service.yaml || exit $?

# Apply Health Check CronJob template
kubectl apply -f postgresql-sdk-health-check.yaml || exit $?

# Wait for sync to complete
echo "Waiting for schema sync to complete..."
kubectl wait --for=condition=complete --timeout=300s job/postgresql-sdk-sync || {
    echo "Schema sync failed or timed out"
    kubectl logs job/postgresql-sdk-sync
    exit 1
}

# Ensure CronJob is not suspended
kubectl patch cronjob postgresql-sdk-health-check -p '{"spec":{"suspend":false}}' 2>/dev/null || true

echo ""
echo "PostgreSQL SDK Service started successfully"
echo "  - Schema synchronized (initialized or upgraded)"
echo "  - Health checks running every 5 minutes"

popd > /dev/null
