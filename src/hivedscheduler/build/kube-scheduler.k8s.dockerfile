# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.26.6 AS builder

ARG TARGETOS
ARG TARGETARCH
ARG GO_RUNNER_COMMIT=b044ae2b55cf464c150607d70e29f4b2d772d505

WORKDIR /go

RUN git clone --branch v1.33.7 --depth 1 https://github.com/kubernetes/kubernetes.git kubernetes

WORKDIR /go/kubernetes

RUN for modfile in $(find . -name 'go.mod' -not -path './vendor/*'); do \
      dir=$(dirname "$modfile"); \
      (cd "$dir" && \
        go get golang.org/x/net@v0.56.0 && \
        go get golang.org/x/text@v0.39.0 && \
        go get go.opentelemetry.io/otel/sdk@v1.43.0 \
      ) || true; \
    done && \
    for modfile in $(find . -name 'go.mod' -not -path './vendor/*'); do \
      dir=$(dirname "$modfile"); \
      (cd "$dir" && go get google.golang.org/grpc@v1.82.1) || true; \
      (cd "$dir" && go get github.com/google/cel-go@v0.29.0) || true; \
      (cd "$dir" && go get golang.org/x/crypto@v0.55.0) || true; \
    done && \
    go work vendor

RUN GOTOOLCHAIN=go1.26.6 KUBE_BUILD_PLATFORMS=linux/${TARGETARCH} \
    make WHAT=cmd/kube-scheduler

RUN git init /go/release && \
    cd /go/release && \
    git remote add origin https://github.com/kubernetes/release.git && \
    git fetch --depth 1 origin ${GO_RUNNER_COMMIT} && \
    git checkout --detach FETCH_HEAD && \
    cd images/build/go-runner && \
    CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} \
      go build -ldflags '-s -w -buildid= -extldflags "-static"' \
      -o /go-runner .

FROM registry.k8s.io/build-image/go-runner:v2.4.0-go1.26.5-bookworm.0
COPY --from=builder /go-runner /go-runner
COPY --from=builder /go/kubernetes/_output/local/go/bin/kube-scheduler /usr/local/bin/kube-scheduler
