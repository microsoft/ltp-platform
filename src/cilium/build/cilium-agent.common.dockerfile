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

# Build cilium agent from source with updated Go.
# This fixes Go stdlib and grpc vulnerabilities by compiling with Go 1.24.13
# (latest 1.24.x patch, up from 1.24.11 used by upstream v1.18.6).
# Runtime base is the official cilium-runtime image (Ubuntu 24.04 + LLVM + BPF tools)
# with OS-level security patches applied.
#

ARG GOLANG_VERSION=1.24.13
ARG CILIUM_VERSION=v1.18.6
ARG CILIUM_RUNTIME_IMAGE=quay.io/cilium/cilium-runtime:aee2ef3503e1a74ba2bd97250a5138951fd55e35@sha256:8518245c6c0392c6e50e7f658c0956cfbbd9fdbdb9dabe2effc69db74bdaf623
ARG CILIUM_ENVOY_IMAGE=quay.io/cilium/cilium-envoy:v1.35.9-1767794330-db497dd19e346b39d81d7b5c0dedf6c812bcc5c9@sha256:81398e449f2d3d0a6a70527e4f641aaa685d3156bea0bb30712fae3fd8822b86

# Stage 1: Build all Go binaries from source with Go 1.24.13
FROM golang:${GOLANG_VERSION} AS builder
ARG CILIUM_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends git make && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /go/src/github.com/cilium/cilium
RUN git clone --depth 1 --branch ${CILIUM_VERSION} \
    https://github.com/cilium/cilium.git .

# Build all cilium-agent container binaries:
#   cilium-dbg, daemon (cilium-agent), cilium-health, bugtool,
#   mount, sysctlfix, cilium-cni
# Then install binaries + BPF source files to /tmp/install
RUN mkdir -p /tmp/install && \
    make DESTDIR=/tmp/install PKG_BUILD=1 \
    build-container install-container-binary

# Build hubble CLI
RUN cd hubble && make && mv hubble /tmp/install/usr/bin/hubble

# Generate licenses and bash completion
RUN make DESTDIR=/tmp/install PKG_BUILD=1 install-bash-completion && \
    make licenses-all && mv LICENSE.all /tmp/install/LICENSE.all

# Copy init/CNI scripts
RUN cp images/cilium/init-container.sh /tmp/install/ && \
    cp plugins/cilium-cni/install-plugin.sh /tmp/install/ && \
    cp plugins/cilium-cni/cni-uninstall.sh /tmp/install/

# Stage 2: Envoy binaries from official image
FROM ${CILIUM_ENVOY_IMAGE} AS cilium-envoy

# Stage 3: Runtime image (LLVM, BPF tools, iptables, gops, CNI already included)
FROM ${CILIUM_RUNTIME_IMAGE} AS release

# Apply latest Ubuntu security updates (fixes libc6, libgnutls30t64, libsystemd0)
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN echo ". /etc/profile.d/bash_completion.sh" >> /etc/bash.bashrc
COPY --from=cilium-envoy /usr/lib/libcilium.so /usr/lib/libcilium.so
COPY --from=cilium-envoy /usr/bin/cilium-envoy /usr/bin/cilium-envoy-starter /usr/bin/
ENV HUBBLE_SERVER=unix:///var/run/cilium/hubble.sock
COPY --from=builder /tmp/install /
RUN /usr/bin/hubble completion bash > /etc/bash_completion.d/hubble
WORKDIR /home/cilium
ENV INITSYSTEM="SYSTEMD"
CMD ["/usr/bin/cilium-dbg"]
