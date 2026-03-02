# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.24.13 as build
ARG TARGETOS
ARG TARGETARCH

ARG CGO_ENABLED=0
ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN git clone --branch 1.31.4-0.1.0 --single-branch https://github.com/everpeace/k8s-host-device-plugin.git /go/src/k8s-host-device-plugin

WORKDIR /go/src/k8s-host-device-plugin

RUN go mod edit -go=1.24 -toolchain=go1.24.13

RUN go mod edit \
    -require=github.com/fsnotify/fsnotify@v1.9.0 \
    -require=golang.org/x/net@v0.40.0 \
    -require=google.golang.org/grpc@v1.72.1 \
    -require=k8s.io/kubelet@v0.33.1

RUN go mod tidy -go=1.24.13

RUN go install -ldflags="-s -w"

FROM gcr.io/distroless/static-debian12
COPY --from=build /go/bin/k8s-host-device-plugin /bin/k8s-host-device-plugin

CMD ["/bin/k8s-host-device-plugin"]

