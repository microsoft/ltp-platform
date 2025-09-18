#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -xe

DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install libfuse3-dev fuse3 blobfuse2 -y || echo "Failed to install fuse"
INSTALLED_VERSION=$(blobfuse2 --version | grep -oP '\d+\.\d+\.\d+')
REQUIRED_VERSION="2.5.0"

if dpkg --compare-versions "$INSTALLED_VERSION" "lt" "$REQUIRED_VERSION"; then
    echo "Updating blobfuse2 to a version newer than $REQUIRED_VERSION"
    DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade blobfuse2 -y || echo "Failed to update blobfuse2"
else
    echo "blobfuse2 is already up-to-date (version $INSTALLED_VERSION)"
fi