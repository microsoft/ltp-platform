#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -xe

DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install libfuse3-dev fuse3 blobfuse2 -y || echo "Failed to install fuse"