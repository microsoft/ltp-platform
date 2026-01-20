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


FROM mcr.microsoft.com/mirror/nvcr/nvidia/cuda:12.0.1-runtime-ubuntu22.04

ARG TARGETARCH
ARG ROCM_VERSION=6.2.2
ARG AMDGPU_VERSION=6.2.2
ARG DCGM_TARGET_VERSION = "1:4.4.1-1"

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  bash \
  curl \
  gnupg \
  wget \
  ca-certificates \
  python3-pip \
  python3-dev \
  sudo && \
  if [ "$TARGETARCH" = "amd64" ]; then \
    printf "Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600" | tee /etc/apt/preferences.d/rocm-pin-600 && \
    curl -sL https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add - && \
    echo "deb https://repo.radeon.com/rocm/apt/$ROCM_VERSION/ jammy main" | tee /etc/apt/sources.list.d/rocm.list && \
    echo "deb https://repo.radeon.com/amdgpu/$AMDGPU_VERSION/ubuntu jammy main" | tee /etc/apt/sources.list.d/amdgpu.list && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends rocm-dev rdc; \
  fi

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
  datacenter-gpu-manager-4-cuda12=${DCGM_TARGET_VERSION} \
  datacenter-gpu-manager-4-core=${DCGM_TARGET_VERSION} \
  datacenter-gpu-manager-4-proprietary-cuda12=${DCGM_TARGET_VERSION}

ENV NERDCTL_VERSION=2.2.1
RUN wget -O /tmp/nerdctl.tar.gz https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-${TARGETARCH}.tar.gz && \
    mkdir -p /tmp/nerdctl && \
    tar -xzvf /tmp/nerdctl.tar.gz -C /tmp/nerdctl && \
    mv /tmp/nerdctl/nerdctl /usr/local/bin/nerdctl && \
    mkdir -p /job_exporter && \
    rm -rf /tmp/nerdctl*

RUN python3 -m pip install prometheus_client psutil filelock

COPY src/Moneo /Moneo

ENV PATH="${PATH}:/opt/rocm/bin"
COPY build/moneo-*-exporter_entrypoint.sh ./

RUN [ -d /opt/rocm/lib ] && echo "/opt/rocm/lib" > /etc/ld.so.conf.d/rocm.conf; \
    [ -d /opt/rocm/rdc/lib ] && echo "/opt/rocm/rdc/lib" >> /etc/ld.so.conf.d/rocm.conf; \
    [ -d /opt/rocm/llvm/lib ] && echo "/opt/rocm/llvm/lib" >> /etc/ld.so.conf.d/rocm.conf

RUN ldconfig

COPY requirements.txt /job_exporter/
RUN pip3 install -r /job_exporter/requirements.txt

RUN apt update && apt upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY src/*.py /job_exporter/
