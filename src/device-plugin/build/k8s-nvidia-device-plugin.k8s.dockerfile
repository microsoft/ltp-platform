# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM nvcr.io/nvidia/k8s-device-plugin:v0.18.0

RUN apt update && apt upgrade -y &&  apt-get clean && \
  rm -rf /var/lib/apt/lists/*