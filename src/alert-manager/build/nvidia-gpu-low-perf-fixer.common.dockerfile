# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM nvidia/cuda:12.2.2-base-ubuntu22.04

COPY ./src/nvidia-gpu-low-perf-fixer .

ENTRYPOINT /bin/bash nvidia-gpu-low-perf-fixer.sh
