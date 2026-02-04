# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.25.6 AS builder

ARG TARGETOS
ARG TARGETARCH

WORKDIR /go

RUN git clone --branch v1.35.0 --depth 1 https://github.com/kubernetes/kubernetes.git kubernetes

WORKDIR /go/kubernetes

RUN GOTOOLCHAIN=go1.25.6 KUBE_BUILD_PLATFORMS=linux/${TARGETARCH} \
    make WHAT=cmd/kube-scheduler

FROM registry.k8s.io/build-image/go-runner:v2.4.0-go1.25.6-bookworm.0

COPY --from=builder /go/kubernetes/_output/local/go/bin/kube-scheduler /usr/local/bin/kube-scheduler
