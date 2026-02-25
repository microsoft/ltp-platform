# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


############################
# builder: only for compiling python wheels
############################
FROM ubuntu:22.04 AS builder

ARG TARGETARCH

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        python3-pip \
        python3-dev \
        build-essential \
        gcc; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /w

# build wheels once
COPY requirements.txt /w/requirements.txt
RUN python3 -m pip install --no-cache-dir -U pip wheel && \
    python3 -m pip wheel --no-cache-dir --wheel-dir /w/wheels \
        -r /w/requirements.txt \
        prometheus_client psutil filelock


############################
# nerdctl-builder: build nerdctl from source
############################
FROM golang:1.25.7 AS nerdctl-builder

ARG TARGETARCH
ARG NERDCTL_VERSION=2.2.1

WORKDIR /build

RUN set -eux; \
    git clone --depth 1 --branch v${NERDCTL_VERSION} https://github.com/containerd/nerdctl.git .; \
    make binaries; \
    mkdir -p /opt/nerdctl; \
    cp _output/nerdctl /opt/nerdctl/nerdctl; \
    chmod +x /opt/nerdctl/nerdctl


############################
# runtime: minimal CUDA base with only essential components
############################
FROM mcr.microsoft.com/mirror/nvcr/nvidia/cuda:12.0.1-base-ubuntu22.04

ARG TARGETARCH
ARG ROCM_VERSION=6.2.2
ARG AMDGPU_VERSION=6.2.2
ARG DCGM_TARGET_VERSION=1:4.4.1-1

# --------------------------
# Install all components in single layer for size optimization
# --------------------------
RUN set -eux; \
    # Base setup
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        gnupg \
        python3 \
        kmod; \
    # ROCm (runtime only) for AMD GPUs
    if [ "$TARGETARCH" = "amd64" ]; then \
        printf "Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600" \
            > /etc/apt/preferences.d/rocm-pin-600; \
        curl -sL https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add -; \
        echo "deb https://repo.radeon.com/rocm/apt/$ROCM_VERSION/ jammy main" \
            > /etc/apt/sources.list.d/rocm.list; \
        echo "deb https://repo.radeon.com/amdgpu/$AMDGPU_VERSION/ubuntu jammy main" \
            > /etc/apt/sources.list.d/amdgpu.list; \
        apt-get update; \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends rdc amd-smi-lib; \
    fi; \
    # DCGM for GPU monitoring (NVIDIA)
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        datacenter-gpu-manager-4-core=${DCGM_TARGET_VERSION} \
        datacenter-gpu-manager-4-cuda12=${DCGM_TARGET_VERSION} \
        datacenter-gpu-manager-4-proprietary-cuda12=${DCGM_TARGET_VERSION}; \
    # Clean up everything in single layer
    apt-get remove -y curl gnupg; \
    apt-get autoremove -y; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/* /var/tmp/*

# --------------------------
# nerdctl (copy from nerdctl-builder)
# --------------------------
COPY --from=nerdctl-builder /opt/nerdctl/nerdctl /usr/local/bin/nerdctl

# --------------------------
# python runtime deps (from wheels)
# --------------------------

COPY --from=builder /w/wheels /wheels
COPY requirements.txt /job_exporter/requirements.txt

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-pip; \
    python3 -m pip install --no-cache-dir -U pip && \
    python3 -m pip install --no-cache-dir \
        --no-index --find-links=/wheels \
        -r /job_exporter/requirements.txt && \
    python3 -m pip install --no-cache-dir \
        --no-index --find-links=/wheels \
        prometheus_client psutil filelock && \
    # Set environment variable to allow sudo removal during autoremove
    SUDO_FORCE_REMOVE=yes apt-get autoremove -y; \
    apt-get clean; \
    rm -rf /wheels /root/.cache /var/lib/apt/lists/* /var/cache/apt/* /tmp/* /var/tmp/*

# --------------------------
# app files
# --------------------------
COPY src/Moneo /Moneo
COPY src/*.py /job_exporter/
COPY build/moneo-*-exporter_entrypoint.sh ./

# --------------------------
# Final cleanup: remove unnecessary CUDA files to reduce image size
# --------------------------
RUN set -eux; \
    # Remove CUDA static libraries (we only need shared libs for runtime)
    find /usr/local/cuda-12.0 -name "*.a" -delete 2>/dev/null || true; \
    find /usr/local/cuda-12.0 -name "*.la" -delete 2>/dev/null || true; \
    # Remove CUDA development tools and samples
    rm -rf /usr/local/cuda-12.0/nsight* \
        /usr/local/cuda-12.0/libnvvp \
        /usr/local/cuda-12.0/doc \
        /usr/local/cuda-12.0/samples \
        /usr/local/cuda-12.0/extras \
        2>/dev/null || true; \
    # Remove documentation and man pages
    rm -rf /usr/share/doc/* \
        /usr/share/man/* \
        /usr/share/info/* \
        2>/dev/null || true; \
    # Final cache cleanup
    rm -rf /var/cache/* /tmp/* /var/tmp/* 2>/dev/null || true
