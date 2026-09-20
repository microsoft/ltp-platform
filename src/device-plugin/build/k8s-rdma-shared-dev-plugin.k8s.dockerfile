# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.25.13-alpine3.23 as builder

ARG TARGETOS
ARG TARGETARCH

ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN apk add --no-cache git make

RUN git clone --depth 1 --branch v1.5.4 \
    https://github.com/Mellanox/k8s-rdma-shared-dev-plugin.git \
    /usr/src/k8s-rdma-shared-dp

ENV HTTP_PROXY $http_proxy
ENV HTTPS_PROXY $https_proxy

RUN apk add --no-cache --virtual build-base linux-headers
WORKDIR /usr/src/k8s-rdma-shared-dp

RUN go get golang.org/x/text@v0.39.0 && \
    go get golang.org/x/crypto@v0.53.0 && \
    go get golang.org/x/net@v0.56.0 && \
    go get golang.org/x/mod@v0.40.0 && \
    go get google.golang.org/grpc@v1.83.2

RUN CGO_ENABLED=0 go build -o build/k8s-rdma-shared-dp -tags no_openssl -mod=mod -ldflags "-s -w" ./cmd/k8s-rdma-shared-dp

FROM alpine:3.23
RUN apk add --no-cache hwdata-pci
COPY --from=builder /usr/src/k8s-rdma-shared-dp/build/k8s-rdma-shared-dp /bin/

RUN apk update && apk upgrade && \
    rm -rf /var/cache/apk/*

LABEL io.k8s.display-name="RDMA Shared Device Plugin"

CMD ["/bin/k8s-rdma-shared-dp"]
