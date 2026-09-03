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
# This fixes Go stdlib and grpc vulnerabilities by compiling with Go 1.25.13
# (latest 1.25.x patch). All Go binaries (cilium, hubble, CNI plugins) are
# compiled from source so no pre-built binaries from the base image are used.
# Runtime base is the official cilium-runtime image (Ubuntu 24.04 + LLVM + BPF tools)
# with OS-level security patches applied.
#

ARG GOLANG_VERSION=1.25.13
ARG CILIUM_VERSION=v1.18.10
ARG CNI_PLUGINS_VERSION=v1.9.0
ARG GOPS_VERSION=v0.3.27
ARG CILIUM_RUNTIME_IMAGE=quay.io/cilium/cilium-runtime:5615e8b62b0b47ad5a586bf459d0c072eaa0442a@sha256:5edc984f0a8f4ae208d60490a3234d1950b5497d2646980328e69f4a73c50e85
ARG CILIUM_ENVOY_IMAGE=quay.io/cilium/cilium-envoy:v1.36.6-1778235340-b87d1e32f522b33bd51701c6476d199326f01496@sha256:71d4fa0ec45e8d546dbd5604e169dc77fe92be63b799313bff031d00d89762e3

# Stage 1: Build all Go binaries from source with the patched Go toolchain
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

RUN go get golang.org/x/net@v0.56.0 && \
    go get golang.org/x/text@v0.39.0 && \
    go get google.golang.org/grpc@v1.82.1 && \
    go get github.com/google/cel-go@v0.29.0 && \
    go get go.mongodb.org/mongo-driver@v1.17.7 && \
    go get github.com/gopacket/gopacket@v1.7.1 && \
    go get github.com/cilium/ebpf@v0.22.0 && \
    go get golang.org/x/crypto@v0.55.0 && \
    go mod tidy && \
    go mod vendor

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
