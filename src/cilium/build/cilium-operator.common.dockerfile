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

# Build cilium-operator-generic from source with updated Go.
# This fixes Go stdlib and grpc vulnerabilities by compiling with Go 1.25.11
# (latest 1.25.x patch). The operator is a pure Go binary (CGO_ENABLED=0, scratch base).
#

ARG GOLANG_VERSION=1.25.11
ARG CILIUM_VERSION=v1.18.10

# Stage 1: Build operator binary
FROM golang:${GOLANG_VERSION} AS builder
ARG CILIUM_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends git make && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /go/src/github.com/cilium/cilium
RUN git clone --depth 1 --branch ${CILIUM_VERSION} \
    https://github.com/cilium/cilium.git .

RUN go get golang.org/x/crypto@v0.52.0 && \
    go get golang.org/x/net@v0.55.0 && \
    go mod tidy && \
    go mod vendor

RUN mkdir -p /out && \
    make -C operator cilium-operator-generic && \
    mv operator/cilium-operator-generic /out/cilium-operator-generic

# Stage 2: CA certificates
FROM alpine:3.23 AS certs
RUN apk --update add ca-certificates

# Stage 3: Minimal runtime (scratch)
FROM scratch
COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=builder /out/cilium-operator-generic /usr/bin/cilium-operator-generic
COPY --chmod=777 --from=scratch / /home/gops
ENV GOPS_CONFIG_DIR=/home/gops
WORKDIR /
CMD ["/usr/bin/cilium-operator-generic"]
