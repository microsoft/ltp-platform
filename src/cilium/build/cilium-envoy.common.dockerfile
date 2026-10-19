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

# Rebuild the bundled Go components and apply the latest OS security patches.
# Base: official cilium-envoy matching cilium v1.20.3
# Keep the upstream Envoy and starter binaries unchanged.
#

ARG CILIUM_ENVOY_TAG=v1.38.6-1791537840-00e749f11f69334c625e53fc1ce2fc6c7f34a51f
FROM golang:1.26.9 AS healthcheck-builder
ARG CILIUM_ENVOY_TAG
ARG TARGETOS
ARG TARGETARCH
ENV GOTOOLCHAIN=local
WORKDIR /src

RUN git init . && \
    git fetch --depth 1 https://github.com/cilium/proxy.git "${CILIUM_ENVOY_TAG##*-}" && \
    git checkout --detach FETCH_HEAD && \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
      go build -trimpath -ldflags="-s -w" \
      -o /out/cilium-envoy-healthcheck ./healthcheck/main.go

# Keep the upstream proxylib toolchain and a glibc baseline below Ubuntu 24.04.
FROM golang:1.27.2-bookworm AS proxylib-builder
ARG TARGETOS
ARG TARGETARCH
ENV GOTOOLCHAIN=local
WORKDIR /src
COPY --from=healthcheck-builder /src/ ./

RUN go get golang.org/x/net@v0.60.0 && \
    GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
      make -C proxylib GO_BUILD_FLAGS="-mod=mod -trimpath"

FROM quay.io/cilium/cilium-envoy:${CILIUM_ENVOY_TAG}@sha256:d6c8c0c91954d1885026d82a31b341f37dcd34a4b127fdaf1587e43ddd224cef

# Apply latest Ubuntu security updates
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY --from=healthcheck-builder /out/cilium-envoy-healthcheck /usr/bin/cilium-envoy-healthcheck
COPY --from=proxylib-builder /src/proxylib/libcilium.so /usr/lib/libcilium.so
