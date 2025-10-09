#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -xe

wait_for_dpkg_lock() {
    if ! timeout 300 bash -c \
        'while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
                 || pgrep -x "apt|apt-get|dpkg|unattended-upgrades" >/dev/null; do
             sleep 3
         done'
    then
        echo "Timed out waiting for dpkg lock."
        exit 124
    fi
    bash -c 'exec "$@"' -- "$@"
}

wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get update -y'
wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install libfuse3-dev fuse3 blobfuse2 -y || echo "Failed to install fuse"'

# Check if blobfuse2 is installed
if ! command -v blobfuse2 >/dev/null 2>&1; then
    echo "blobfuse2 is not installed. Exiting."
    exit 1
fi

INSTALLED_VERSION=$(blobfuse2 --version | grep -oP '\d+\.\d+\.\d+')
REQUIRED_VERSION="2.5.0"

# Check if version extraction succeeded
if [ -z "$INSTALLED_VERSION" ]; then
    echo "Failed to extract blobfuse2 version. Exiting."
    exit 1
fi

if dpkg --compare-versions "$INSTALLED_VERSION" "lt" "$REQUIRED_VERSION"; then
    echo "Updating blobfuse2 to a version newer than $REQUIRED_VERSION"
    wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade blobfuse2 -y || echo "Failed to update blobfuse2"'
else
    echo "blobfuse2 is already up-to-date (version $INSTALLED_VERSION)"
fi