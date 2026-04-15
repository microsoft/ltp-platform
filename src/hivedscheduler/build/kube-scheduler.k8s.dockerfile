# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.25.9 AS builder

ARG TARGETOS
ARG TARGETARCH

WORKDIR /go

RUN git clone --branch v1.33.7 --depth 1 https://github.com/kubernetes/kubernetes.git kubernetes

WORKDIR /go/kubernetes

RUN for modfile in $(find . -name 'go.mod' -not -path './vendor/*'); do \
      dir=$(dirname "$modfile"); \
      (cd "$dir" && \
        go get golang.org/x/crypto@v0.45.0 && \
        go get go.opentelemetry.io/otel/sdk@v1.43.0 \
      ) || true; \
    done && \
    for modfile in $(find . -name 'go.mod' -not -path './vendor/*'); do \
      dir=$(dirname "$modfile"); \
      (cd "$dir" && go get google.golang.org/grpc@v1.79.3) || true; \
    done && \
    go work vendor

RUN GOTOOLCHAIN=go1.25.9 KUBE_BUILD_PLATFORMS=linux/${TARGETARCH} \
    make WHAT=cmd/kube-scheduler

FROM registry.k8s.io/build-image/go-runner:v2.4.0-go1.25.9-bookworm.0

COPY --from=builder /go/kubernetes/_output/local/go/bin/kube-scheduler /usr/local/bin/kube-scheduler
