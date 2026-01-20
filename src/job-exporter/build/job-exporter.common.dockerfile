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
FROM mcr.microsoft.com/mirror/nvcr/nvidia/cuda:12.0.1-runtime-ubuntu22.04 AS builder

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
# runtime: final image
############################
FROM mcr.microsoft.com/mirror/nvcr/nvidia/cuda:12.0.1-runtime-ubuntu22.04

ARG TARGETARCH
ARG ROCM_VERSION=6.2.2
ARG AMDGPU_VERSION=6.2.2
ARG DCGM_TARGET_VERSION=1:4.4.1-1

# --------------------------
# base + REQUIRED apt upgrade
# --------------------------
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        gnupg \
        wget \
        python3 \
        python3-pip; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# --------------------------
# ROCm (runtime only)
# --------------------------
RUN set -eux; \
    if [ "$TARGETARCH" = "amd64" ]; then \
        printf "Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600" \
            > /etc/apt/preferences.d/rocm-pin-600; \
        curl -sL https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add -; \
        echo "deb https://repo.radeon.com/rocm/apt/$ROCM_VERSION/ jammy main" \
            > /etc/apt/sources.list.d/rocm.list; \
        echo "deb https://repo.radeon.com/amdgpu/$AMDGPU_VERSION/ubuntu jammy main" \
            > /etc/apt/sources.list.d/amdgpu.list; \
        apt-get update; \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends rdc; \
        rm -rf /var/lib/apt/lists/*; \
    fi

# --------------------------
# DCGM (runtime only, same layer clean)
# --------------------------
RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        datacenter-gpu-manager-4-cuda12=${DCGM_TARGET_VERSION} \
        datacenter-gpu-manager-4-core=${DCGM_TARGET_VERSION} \
        datacenter-gpu-manager-4-proprietary-cuda12=${DCGM_TARGET_VERSION}; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# --------------------------
# nerdctl
# --------------------------
ENV NERDCTL_VERSION=2.2.1
RUN set -eux; \
    wget -O /tmp/nerdctl.tar.gz \
        https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-${TARGETARCH}.tar.gz; \
    mkdir -p /tmp/nerdctl; \
    tar -xzf /tmp/nerdctl.tar.gz -C /tmp/nerdctl; \
    mv /tmp/nerdctl/nerdctl /usr/local/bin/nerdctl; \
    rm -rf /tmp/nerdctl* /tmp/nerdctl.tar.gz

# --------------------------
# python runtime deps (from wheels)
# --------------------------

COPY --from=builder /w/wheels /wheels
COPY requirements.txt /job_exporter/requirements.txt

RUN python3 -m pip install --no-cache-dir -U pip && \  
    python3 -m pip install --no-cache-dir \
        --no-index --find-links=/wheels \
        -r /job_exporter/requirements.txt && \
    python3 -m pip install --no-cache-dir \
        --no-index --find-links=/wheels \
        prometheus_client psutil filelock && \
    rm -rf /wheels

# --------------------------
# app files
# --------------------------
COPY src/Moneo /Moneo
COPY src/*.py /job_exporter/
COPY build/moneo-*-exporter_entrypoint.sh ./
