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
# Register the ROCM package repository, and install rocm-dev package
ARG ROCM_VERSION=6.2.2
ARG AMDGPU_VERSION=6.2.2
ARG APT_PREF="Package: *\nPin: release o=repo.radeon.com\nPin-Priority: 600"
RUN echo "$APT_PREF" > /etc/apt/preferences.d/rocm-pin-600

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl libnuma-dev gnupg \
  && curl -sL https://repo.radeon.com/rocm/rocm.gpg.key | apt-key add - \
  && printf "deb [arch=amd64] https://repo.radeon.com/rocm/apt/$ROCM_VERSION/ jammy main" | tee /etc/apt/sources.list.d/rocm.list \
  && printf "deb [arch=amd64] https://repo.radeon.com/amdgpu/$AMDGPU_VERSION/ubuntu jammy main" | tee /etc/apt/sources.list.d/amdgpu.list \
  && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  sudo \
  libelf1 \
  ibverbs-utils \
  bash \
  kmod \
  file \
  python3-dev \
  python3-pip \
  rocm-dev \
  g++ \
  numactl \
  unzip \
  autoconf \
  libtool \
  pkg-config \
  libgflags-dev \
  libgtest-dev \
  libc++-dev \
  curl \
  libcap-dev \
  git \
  cmake \
  automake \
  build-essential && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN apt update && apt upgrade -y

ARG BRANCH_OR_TAG='ruigao/add_dummy_field_6.2.2update'

# Clone Moneo
RUN git config --global advice.detachedHead false
RUN git clone --branch ${BRANCH_OR_TAG} https://github.com/Azure/Moneo.git

# Install RDC
RUN sudo bash Moneo/src/worker/install/amd.sh

# Install DCGM
RUN sed -i 's/systemctl --now enable nvidia-dcgm/#&/' Moneo/src/worker/install/nvidia.sh && \
    sed -i 's/systemctl start nvidia-dcgm/#&/' Moneo/src/worker/install/nvidia.sh && \
    sudo bash Moneo/src/worker/install/nvidia.sh

ENV PATH "${PATH}:/opt/rocm/bin"
COPY build/moneo-*-exporter_entrypoint.sh .
COPY build/update-dcgm.py .

# For the job exporter
ENV NERDCTL_VERSION=2.0.0-rc.2
RUN apt-get update && apt-get install --no-install-recommends -y wget ca-certificates
RUN wget https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz && \
    mkdir -p /tmp/nerdctl && \
    tar -xzvf nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz -C /tmp/nerdctl && \
    mv /tmp/nerdctl/nerdctl /usr/local/bin/nerdctl && \
    mkdir -p /job_exporter && \
    rm -rf /tmp/nerdctl && \
    rm -rf nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz

COPY requirements.txt /job_exporter/
RUN pip3 install -r /job_exporter/requirements.txt

COPY src/*.py /job_exporter/
