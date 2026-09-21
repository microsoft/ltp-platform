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
ARG PROMETHEUS_VERSION=v3.14.0
ARG TARGETOS
ARG TARGETARCH

FROM ${PROMETHEUS_BUILDER_IMAGE} AS builder
ARG PROMETHEUS_VERSION
ARG TARGETOS
ARG TARGETARCH

WORKDIR /go/src/github.com/prometheus/prometheus
RUN git clone --depth 1 --branch ${PROMETHEUS_VERSION} \
    https://github.com/prometheus/prometheus.git .

RUN go get golang.org/x/crypto@v0.56.0 \
      google.golang.org/grpc@v1.83.2 && \
    go mod tidy && \
    GOOS=${TARGETOS} GOARCH=${TARGETARCH} make build PREFIX=/out

FROM quay.io/prometheus/busybox-${TARGETOS}-${TARGETARCH}:latest
LABEL maintainer="The Prometheus Authors <prometheus-developers@googlegroups.com>"
LABEL org.opencontainers.image.authors="The Prometheus Authors" \
      org.opencontainers.image.vendor="Prometheus" \
      org.opencontainers.image.title="Prometheus" \
      org.opencontainers.image.description="The Prometheus monitoring system and time series database" \
      org.opencontainers.image.source="https://github.com/prometheus/prometheus" \
      org.opencontainers.image.url="https://prometheus.io/" \
      org.opencontainers.image.documentation="https://prometheus.io/docs/introduction/overview/" \
      org.opencontainers.image.licenses="Apache License 2.0" \
      io.prometheus.image.variant="busybox"

COPY --from=builder /out/prometheus /bin/prometheus
COPY --from=builder /out/promtool /bin/promtool
COPY --from=builder /go/src/github.com/prometheus/prometheus/documentation/examples/prometheus.yml /etc/prometheus/prometheus.yml
COPY --from=builder /go/src/github.com/prometheus/prometheus/LICENSE /LICENSE
COPY --from=builder /go/src/github.com/prometheus/prometheus/NOTICE /NOTICE

WORKDIR /prometheus
RUN chown -R nobody:nobody /etc/prometheus /prometheus && chmod g+w /prometheus

USER nobody
EXPOSE 9090
VOLUME ["/prometheus"]
ENTRYPOINT ["/bin/prometheus"]
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/prometheus"]
