# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM nvidia/cuda:12.2.2-base-ubuntu22.04

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/nvidia-gpu-low-perf-fixer .

ENTRYPOINT /bin/bash nvidia-gpu-low-perf-fixer.sh
