# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM docker.io/golang:1.24.3-alpine3.21 as builder

ARG TARGETOS
ARG TARGETARCH

ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN apk --no-cache add git pkgconfig build-base libdrm-dev
RUN apk --no-cache add hwloc-dev --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community

RUN mkdir -p /go/src/github.com/ROCm/k8s-device-plugin
RUN git clone --branch v1.31.0.7 --single-branch https://github.com/ROCm/k8s-device-plugin.git /go/src/github.com/ROCm/k8s-device-plugin

COPY ./build/k8s-rocm-device-plugin-patches/0001-update-toolchain-to-1.24-with-package-updates.patch /go/src/github.com/ROCm/k8s-device-plugin

WORKDIR /go/src/github.com/ROCm/k8s-device-plugin
RUN git apply ./0001-update-toolchain-to-1.24-with-package-updates.patch

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
