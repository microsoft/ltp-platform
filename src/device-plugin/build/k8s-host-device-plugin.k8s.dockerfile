# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.26.8 as build
ARG TARGETOS
ARG TARGETARCH

ARG CGO_ENABLED=0
ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN git clone --branch 1.36.0-0.1.0 --single-branch https://github.com/everpeace/k8s-host-device-plugin.git /go/src/k8s-host-device-plugin

WORKDIR /go/src/k8s-host-device-plugin

RUN go get google.golang.org/grpc@v1.83.2

RUN go mod tidy

RUN go install -ldflags="-s -w"

FROM gcr.io/distroless/static-debian12
COPY --from=build /go/bin/k8s-host-device-plugin /bin/k8s-host-device-plugin

CMD ["/bin/k8s-host-device-plugin"]
