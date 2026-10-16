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

# Build Cilium-owned binaries from source with the official v1.20.3 builder,
# which provides Go 1.26.9 and the required BPF/LLVM build toolchain.
# Runtime utilities such as gops and the loopback CNI plugin remain from the
# matching official runtime image; Pebble is replaced with its patched release.
#

ARG CILIUM_VERSION=v1.20.3
ARG PEBBLE_VERSION=v1.32.2
ARG CILIUM_BUILDER_IMAGE=quay.io/cilium/cilium-builder:2cc44e177a66d543be19c012f7925dea7aeae750@sha256:6cc5b7a4e22595269988b50f5531ae00fd8ec9266c966a0099c86aaebee6cc70
ARG CILIUM_RUNTIME_IMAGE=quay.io/cilium/cilium-runtime:3e883791a0a491f1c3b926e68e0a9b2f0486189d@sha256:0fc05e78f02d344e36766b9ff146ac3c78ff5341bd051efcdcbd650baa0971f5
ARG CILIUM_ENVOY_IMAGE=quay.io/cilium/cilium-envoy:v1.38.6-1791537840-00e749f11f69334c625e53fc1ce2fc6c7f34a51f@sha256:d6c8c0c91954d1885026d82a31b341f37dcd34a4b127fdaf1587e43ddd224cef

# Stage 1: Build Cilium with the builder and commands pinned by upstream v1.20.3.
FROM --platform=${BUILDPLATFORM} ${CILIUM_BUILDER_IMAGE} AS builder
ARG CILIUM_VERSION
ARG PEBBLE_VERSION
ARG TARGETOS
ARG TARGETARCH
ARG BUILDARCH

WORKDIR /workspace/cilium
RUN git clone --depth 1 --branch ${CILIUM_VERSION} \
    https://github.com/cilium/cilium.git .

RUN go get github.com/go-openapi/swag/jsonutils@v0.27.1 && \
    go get github.com/gopacket/gopacket@v1.7.1 && \
    go mod tidy && \
    go mod vendor

# Build and install the same container targets as the upstream Cilium Dockerfile.
RUN make GOARCH=${TARGETARCH} \
    DESTDIR=/tmp/install/${TARGETOS}/${TARGETARCH} \
    PKG_BUILD=1 NOSTRIP=1 \
    build-container install-container-binary

# Match upstream release stripping after retaining symbols during compilation.
RUN set -xe && \
    cd /tmp/install/${TARGETOS}/${TARGETARCH} && \
    find . -type f -executable -exec sh -c \
      'objcopy_cmd=objcopy; \
       if [ "${TARGETARCH}" = "amd64" ]; then objcopy_cmd=x86_64-linux-gnu-objcopy; \
       elif [ "${TARGETARCH}" = "arm64" ]; then objcopy_cmd=aarch64-linux-gnu-objcopy; fi; \
       filename=$(basename "$0"); \
       "$objcopy_cmd" --only-keep-debug "$0" "$0.debug"; \
       "$objcopy_cmd" --strip-all "$0"; \
       (cd "$(dirname "$0")" && "$objcopy_cmd" --add-gnu-debuglink="${filename}.debug" "$filename"); \
       rm "$0.debug"' \
      {} \;

# Replace the runtime base's Pebble binary with a patched release.
RUN GOOS=${TARGETOS} GOARCH=${TARGETARCH} CGO_ENABLED=0 \
    GOBIN=/tmp/pebble-bin go install -trimpath -ldflags="-s -w" \
      github.com/canonical/pebble/cmd/pebble@${PEBBLE_VERSION} && \
    install -m 0755 /tmp/pebble-bin/pebble \
      /tmp/install/${TARGETOS}/${TARGETARCH}/usr/bin/pebble

# Generate licenses and bash completion
RUN make GOARCH=${BUILDARCH} \
      DESTDIR=/tmp/install/${TARGETOS}/${TARGETARCH} \
      PKG_BUILD=1 install-bash-completion licenses-all && \
    mv LICENSE.all /tmp/install/${TARGETOS}/${TARGETARCH}/LICENSE.all

RUN cp images/cilium/init-container.sh \
      plugins/cilium-cni/install-plugin.sh \
      plugins/cilium-cni/cni-uninstall.sh \
      /tmp/install/${TARGETOS}/${TARGETARCH}/

# Stage 2: Envoy binaries from official image
FROM ${CILIUM_ENVOY_IMAGE} AS cilium-envoy

# Stage 3: Runtime image (LLVM, BPF tools, iptables, gops, CNI already included)
FROM ${CILIUM_RUNTIME_IMAGE} AS release
ARG TARGETOS
ARG TARGETARCH

# Apply latest Ubuntu security updates (fixes libc6, libgnutls30t64, libsystemd0)
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN echo ". /etc/profile.d/bash_completion.sh" >> /etc/bash.bashrc
COPY --from=cilium-envoy /usr/bin/cilium-envoy /usr/bin/cilium-envoy-starter /usr/bin/
ENV HUBBLE_SERVER=unix:///var/run/cilium/hubble.sock
COPY --from=builder /tmp/install/${TARGETOS}/${TARGETARCH} /
RUN /usr/bin/hubble completion bash > /etc/bash_completion.d/hubble
WORKDIR /home/cilium
ENV INITSYSTEM="SYSTEMD"
CMD ["/usr/bin/cilium-dbg"]
