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
# Register the ROCM package repository, and install rocm-dev package
ARG ROCM_VERSION=6.2.2
ARG AMDGPU_VERSION=6.2.2

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  autoconf \
  automake \
  bash \
  build-essential \
  cmake \
  curl \
  file \
  g++ \
  git \
  gnupg \
  ibverbs-utils \
  kmod \
  libc++-dev \
  libcap-dev \
  libelf1 \
  libgflags-dev \
  libgtest-dev \
  libnuma-dev \
  libtool \
  numactl \
  pkg-config \
  python3-dev \
  python3-pip \
  sudo \
  unzip && \
  if [ "$TARGETARCH" = "amd64" ]; then \
    printf "Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600" | tee /etc/apt/preferences.d/rocm-pin-600 && \
    curl -sL https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add - && \
    echo "deb https://repo.radeon.com/rocm/apt/$ROCM_VERSION/ jammy main" | tee /etc/apt/sources.list.d/rocm.list && \
    echo "deb https://repo.radeon.com/amdgpu/$AMDGPU_VERSION/ubuntu jammy main" | tee /etc/apt/sources.list.d/amdgpu.list && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends rocm-dev; \
  fi

COPY src/Moneo /Moneo

# Install RDC
RUN if [ "$TARGETARCH" = "amd64" ]; then sudo bash Moneo/src/worker/install/amd.sh; fi

# Install DCGM
RUN sed -i 's/systemctl --now enable nvidia-dcgm/#&/' Moneo/src/worker/install/nvidia.sh && \
    sed -i 's/systemctl start nvidia-dcgm/#&/' Moneo/src/worker/install/nvidia.sh && \
    sudo bash Moneo/src/worker/install/nvidia.sh

ENV PATH="${PATH}:/opt/rocm/bin"
COPY build/moneo-*-exporter_entrypoint.sh ./
COPY build/update-dcgm.py .

# For the job exporter
ENV NERDCTL_VERSION=2.1.3
RUN apt-get update && apt-get install --no-install-recommends -y wget ca-certificates
RUN wget -O /tmp/nerdctl.tar.gz https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-${TARGETARCH}.tar.gz && \
    mkdir -p /tmp/nerdctl && \
    tar -xzvf /tmp/nerdctl.tar.gz -C /tmp/nerdctl && \
    mv /tmp/nerdctl/nerdctl /usr/local/bin/nerdctl && \
    mkdir -p /job_exporter && \
    rm -rf /tmp/nerdctl*

COPY requirements.txt /job_exporter/
RUN pip3 install -r /job_exporter/requirements.txt

# For DCGM missing logger module
RUN pip3 install logger

RUN apt update && apt upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY src/*.py /job_exporter/
