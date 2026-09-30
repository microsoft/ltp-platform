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

ARG PROMETHEUS_BUILDER_IMAGE=quay.io/prometheus/golang-builder:1.26-base
ARG NODE_EXPORTER_VERSION=v1.12.1
ARG TARGETOS
ARG TARGETARCH

FROM ${PROMETHEUS_BUILDER_IMAGE} AS builder
ARG NODE_EXPORTER_VERSION
ARG TARGETOS
ARG TARGETARCH

WORKDIR /go/src/github.com/prometheus/node_exporter
RUN git clone --depth 1 --branch ${NODE_EXPORTER_VERSION} \
    https://github.com/prometheus/node_exporter.git .

RUN go get golang.org/x/crypto@v0.56.0 && \
    go mod tidy && \
    GOOS=${TARGETOS} GOARCH=${TARGETARCH} make build PREFIX=/out

FROM quay.io/prometheus/busybox-${TARGETOS}-${TARGETARCH}:latest
LABEL maintainer="The Prometheus Authors <prometheus-developers@googlegroups.com>"
LABEL org.opencontainers.image.authors="The Prometheus Authors"
LABEL org.opencontainers.image.vendor="Prometheus"
LABEL org.opencontainers.image.title="node_exporter"
LABEL org.opencontainers.image.description="Prometheus exporter for hardware and OS metrics exposed by *NIX kernels"
LABEL org.opencontainers.image.source="https://github.com/prometheus/node_exporter"
LABEL org.opencontainers.image.url="https://github.com/prometheus/node_exporter"
LABEL org.opencontainers.image.documentation="https://github.com/prometheus/node_exporter"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL io.prometheus.image.variant="busybox"

COPY --from=builder /out/node_exporter /bin/node_exporter

EXPOSE 9100
USER nobody
ENTRYPOINT ["/bin/node_exporter"]
