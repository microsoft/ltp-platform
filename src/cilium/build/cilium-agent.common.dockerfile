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
# This fixes Go stdlib and grpc vulnerabilities by compiling with Go 1.25.9
# (latest 1.25.x patch). All Go binaries (cilium, hubble, CNI plugins) are
# compiled from source so no pre-built binaries from the base image are used.
# Runtime base is the official cilium-runtime image (Ubuntu 24.04 + LLVM + BPF tools)
# with OS-level security patches applied.
#

ARG GOLANG_VERSION=1.25.9
ARG CILIUM_VERSION=v1.18.8
ARG CNI_PLUGINS_VERSION=v1.9.0
ARG GOPS_VERSION=v0.3.27
ARG CILIUM_RUNTIME_IMAGE=quay.io/cilium/cilium-runtime:8f79229999eadc0ced8eacdfdd3574759246d025@sha256:4b36fa5fdeff01bcb7b5dacc9689539ec7f7cdf4a4b758933b0c5b5523a1069a
ARG CILIUM_ENVOY_IMAGE=quay.io/cilium/cilium-envoy:v1.35.9-1773656288-7b052e66eb2cfc5ac130ce0a5be66202a10d83be@sha256:60031f39669542b21aedf05a3317d14e8d3ea48255790af039b315a1c9637361

# Stage 1: Build all Go binaries from source with Go 1.25.9
FROM golang:${GOLANG_VERSION} AS builder
ARG CILIUM_VERSION
ARG CNI_PLUGINS_VERSION
ARG GOPS_VERSION

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

# Build CNI plugins (loopback, etc.) from source to replace pre-built binaries
RUN git clone --depth 1 --branch ${CNI_PLUGINS_VERSION} \
    https://github.com/containernetworking/plugins.git /tmp/cni-plugins && \
    cd /tmp/cni-plugins && \
    CGO_ENABLED=0 go build -o /tmp/install/cni/loopback ./plugins/main/loopback

# Build gops from source to replace pre-built binary in runtime image
RUN CGO_ENABLED=0 go install -ldflags="-s -w" github.com/google/gops@${GOPS_VERSION} && \
    cp /go/bin/gops /tmp/install/usr/bin/gops

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
