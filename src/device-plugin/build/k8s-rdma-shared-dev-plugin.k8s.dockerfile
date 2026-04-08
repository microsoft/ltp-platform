# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.24.13-alpine as builder

ARG TARGETOS
ARG TARGETARCH

ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

RUN apk add --no-cache git make

RUN git clone https://github.com/Mellanox/k8s-rdma-shared-dev-plugin.git /usr/src/k8s-rdma-shared-dp && \
    cd /usr/src/k8s-rdma-shared-dp && \
    git checkout 3069c6eed7b9d368299cfe6080c9859cdbc6ae01

ENV HTTP_PROXY $http_proxy
ENV HTTPS_PROXY $https_proxy

RUN apk add --no-cache --virtual build-base=0.5-r3 linux-headers=5.19.5-r0
WORKDIR /usr/src/k8s-rdma-shared-dp

RUN make clean && \
    make build

FROM alpine:3.21.3
RUN apk add --no-cache hwdata-pci=0.393-r0
COPY --from=builder /usr/src/k8s-rdma-shared-dp/build/k8s-rdma-shared-dp /bin/

RUN apk update && apk upgrade && \
    rm -rf /var/cache/apk/*

LABEL io.k8s.display-name="RDMA Shared Device Plugin"

CMD ["/bin/k8s-rdma-shared-dp"]
