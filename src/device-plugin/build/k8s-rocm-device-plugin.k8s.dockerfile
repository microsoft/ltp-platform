# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM docker.io/golang:1.24.11-alpine3.21 as builder

ARG TARGETOS
ARG TARGETARCH

ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN apk --no-cache add git pkgconfig build-base libdrm-dev
RUN apk --no-cache add hwloc-dev --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community

RUN mkdir -p /go/src/github.com/ROCm/k8s-device-plugin
RUN git clone --branch v1.31.0.7 --single-branch https://github.com/ROCm/k8s-device-plugin.git /go/src/github.com/ROCm/k8s-device-plugin

WORKDIR /go/src/github.com/ROCm/k8s-device-plugin

RUN go mod edit -go=1.24 -toolchain=go1.24.11

RUN go mod edit \
    -require=github.com/go-logr/logr@v1.4.3 \
    -require=github.com/golang/glog@v1.2.5 \
    -require=golang.org/x/net@v0.40.0 \
    -require=google.golang.org/grpc@v1.72.2 \
    -require=google.golang.org/protobuf@v1.36.6 \
    -require=k8s.io/api@v0.33.1 \
    -require=k8s.io/apimachinery@v0.33.1 \
    -require=k8s.io/kubelet@v0.33.1 \
    -require=sigs.k8s.io/controller-runtime@v0.21.0
RUN go mod tidy -go=1.24.11

WORKDIR /go/src/github.com/ROCm/k8s-device-plugin/cmd/k8s-device-plugin

RUN go mod vendor

RUN go install \
    -ldflags="-X main.gitDescribe=$(git -C /go/src/github.com/ROCm/k8s-device-plugin/ describe --always --long --dirty)"

FROM alpine:3.21.3

RUN apk --no-cache add ca-certificates libdrm
RUN apk --no-cache add hwloc --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community
WORKDIR /root/
COPY --from=builder /go/bin/k8s-device-plugin .

RUN apk update && apk upgrade && rm -rf /var/cache/apk/*

CMD ["./k8s-device-plugin", "-logtostderr=true", "-stderrthreshold=INFO", "-v=5"]
