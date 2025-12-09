# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.24 as build
ARG CGO_ENABLED=0
ARG GOOS=linux
ARG GOARCH=amd64

RUN git clone https://github.com/everpeace/k8s-host-device-plugin.git /go/src/k8s-host-device-plugin

WORKDIR /go/src/k8s-host-device-plugin
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go install -ldflags="-s -w"

FROM gcr.io/distroless/static-debian12
COPY --from=build /go/bin/k8s-host-device-plugin /bin/k8s-host-device-plugin

CMD ["/bin/k8s-host-device-plugin"]

#TODO: add arm64 image
