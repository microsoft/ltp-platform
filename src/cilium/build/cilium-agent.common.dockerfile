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

# Build Cilium-owned binaries from source with the official v1.20.2 builder,
# which provides Go 1.26.8 and the required BPF/LLVM build toolchain.
# Runtime utilities such as gops and the loopback CNI plugin remain from the
# matching official runtime image; Pebble is replaced with its patched release.
#

ARG CILIUM_VERSION=v1.20.2
ARG PEBBLE_VERSION=v1.32.2
ARG CILIUM_BUILDER_IMAGE=quay.io/cilium/cilium-builder:e631dcf9a2cbbeb01852013a0262d045e9b23d72@sha256:03c3cd535844e38e9fe61f6715d5991446bb93c8ef5ce60169e8fa4f5c5afbfe
ARG CILIUM_RUNTIME_IMAGE=quay.io/cilium/cilium-runtime:13953be3b88431ba8d71634e240280b1148e6d20@sha256:9f0f69b62f64cc2ce7668c2f07332dd3fc7523e39446f185aa34f26c8f760af9
ARG CILIUM_ENVOY_IMAGE=quay.io/cilium/cilium-envoy:v1.37.6-1789133542-cbec91f666af0bf742da986d43832932dbb26b82@sha256:af7382699576b9e65e9184efa52eeca0b58aea70ad6e511bf260c91d9f740463

# Stage 1: Build Cilium with the builder and commands pinned by upstream v1.20.2.
FROM --platform=${BUILDPLATFORM} ${CILIUM_BUILDER_IMAGE} AS builder
ARG CILIUM_VERSION
ARG PEBBLE_VERSION
ARG TARGETOS
ARG TARGETARCH
ARG BUILDARCH

WORKDIR /workspace/cilium
RUN git clone --depth 1 --branch ${CILIUM_VERSION} \
    https://github.com/cilium/cilium.git .

RUN go get golang.org/x/net@v0.56.0 && \
    go get golang.org/x/text@v0.39.0 && \
    go get google.golang.org/grpc@v1.83.2 && \
    go get github.com/google/cel-go@v0.29.0 && \
    go get go.mongodb.org/mongo-driver@v1.17.7 && \
    go get github.com/gopacket/gopacket@v1.7.1 && \
    go get github.com/cilium/ebpf@v0.22.0 && \
    go get golang.org/x/crypto@v0.56.0 && \
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
