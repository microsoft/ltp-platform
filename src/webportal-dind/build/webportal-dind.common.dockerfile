FROM golang:1.24 as builder

ARG RUNCVERSION=1.4.0

RUN apt update && apt install -y make gcc linux-libc-dev libseccomp-dev pkg-config

RUN git clone -b v${RUNCVERSION} --depth 1 https://github.com/opencontainers/runc.git /go/src/runc

WORKDIR /go/src/runc

RUN make static

FROM ubuntu:latest

RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/lib/docker-vfs

COPY build/install.sh .

RUN chmod +x install.sh

RUN bash ./install.sh

COPY --from=builder /go/src/runc/runc /usr/local/bin/runc