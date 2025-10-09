#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -xe
set -o pipefail

# Log file path
LOG_FILE="/var/log/blobfuse_install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Function to wait for dpkg lock
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

echo "=== Step 1: Update apt cache ==="
wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get update -y'

echo "=== Step 2: Install required tools ==="
wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install curl apt-transport-https ca-certificates -y'

echo "=== Step 3: Add Microsoft blobfuse2 official repository ==="
curl -fsSL https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb -o packages-microsoft-prod.deb
wait_for_dpkg_lock bash -c 'dpkg -i packages-microsoft-prod.deb'
wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get update -y'

echo "=== Step 4: Install dependencies and blobfuse2 specific version (2.5.0) ==="
wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install libfuse3-dev fuse3 blobfuse2=2.5.0 -y || echo "Failed to install blobfuse2 2.5.0"'

echo "=== Step 5: Verify blobfuse2 installation ==="
if ! command -v blobfuse2 >/dev/null 2>&1; then
    echo "blobfuse2 installation failed, exiting."
    exit 1
fi

INSTALLED_VERSION=$(blobfuse2 --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
REQUIRED_VERSION="2.5.0"

if [ -z "$INSTALLED_VERSION" ]; then
    echo "Failed to extract blobfuse2 version. Full output:"
    blobfuse2 --version
    exit 1
fi

echo "Installed version: $INSTALLED_VERSION, Required version: $REQUIRED_VERSION"

if dpkg --compare-versions "$INSTALLED_VERSION" "lt" "$REQUIRED_VERSION"; then
    echo "Current version is lower than $REQUIRED_VERSION, attempting upgrade..."
    wait_for_dpkg_lock bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade blobfuse2 -y || echo "Failed to upgrade blobfuse2"'
else
    echo "blobfuse2 meets the required version (>= $REQUIRED_VERSION)"
fi

echo "=== Installation completed, logs saved to $LOG_FILE ==="