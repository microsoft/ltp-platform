# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

ARG PROMETHEUS_BUILDER_IMAGE=quay.io/prometheus/golang-builder:1.26-base
ARG ALERTMANAGER_VERSION=v0.34.1
ARG NODE_VERSION=24.3.0
ARG TARGETOS
ARG TARGETARCH

FROM node:${NODE_VERSION} AS ui
ARG ALERTMANAGER_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends git make && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /go/src/github.com/prometheus/alertmanager
RUN git clone --depth 1 --branch ${ALERTMANAGER_VERSION} \
    https://github.com/prometheus/alertmanager.git .

RUN make -C ui/app build

FROM ${PROMETHEUS_BUILDER_IMAGE} AS builder
ARG ALERTMANAGER_VERSION
ARG TARGETOS
ARG TARGETARCH

WORKDIR /go/src/github.com/prometheus/alertmanager
RUN git clone --depth 1 --branch ${ALERTMANAGER_VERSION} \
    https://github.com/prometheus/alertmanager.git .

COPY --from=ui /go/src/github.com/prometheus/alertmanager/ui/app/dist ./ui/app/dist
RUN touch ui/app/dist/.build_stamp

RUN go get golang.org/x/crypto@v0.56.0 \
      google.golang.org/grpc@v1.83.2 && \
    go mod tidy && \
    GOOS=${TARGETOS} GOARCH=${TARGETARCH} make build PREFIX=/out

FROM quay.io/prometheus/busybox-${TARGETOS}-${TARGETARCH}:latest
LABEL maintainer="The Prometheus Authors <prometheus-developers@googlegroups.com>"
LABEL org.opencontainers.image.source="https://github.com/prometheus/alertmanager"

COPY --from=builder /out/alertmanager /bin/alertmanager
COPY --from=builder /out/amtool /bin/amtool
COPY --from=builder /go/src/github.com/prometheus/alertmanager/examples/ha/alertmanager.yml /etc/alertmanager/alertmanager.yml
COPY --from=builder /go/src/github.com/prometheus/alertmanager/LICENSE /LICENSE
COPY --from=builder /go/src/github.com/prometheus/alertmanager/NOTICE /NOTICE

RUN mkdir -p /alertmanager && \
    chown -R nobody:nobody /etc/alertmanager /alertmanager && \
    chmod -R g+w /alertmanager

USER nobody
EXPOSE 9093
VOLUME ["/alertmanager"]
WORKDIR /alertmanager
ENTRYPOINT ["/bin/alertmanager"]
CMD ["--config.file=/etc/alertmanager/alertmanager.yml", \
     "--storage.path=/alertmanager"]
