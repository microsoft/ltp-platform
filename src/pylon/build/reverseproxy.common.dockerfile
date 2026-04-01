FROM golang:1.24 AS builder

RUN git clone --branch v0.66.0 --depth 1 https://github.com/fatedier/frp.git /frp
WORKDIR /frp

RUN go get github.com/quic-go/quic-go@v0.57.0 && \
    go get golang.org/x/crypto@v0.45.0 && \
    go get github.com/pion/dtls/v3@v3.1.1 && \
    go mod tidy

RUN make frpc

FROM ubuntu:22.04

# Set up working directory
WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get -y install --no-install-recommends bash curl python3 python3-pip && \
    pip3 install --no-cache-dir jinja2 && \
    apt-get remove -y python3-pip && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /frp/bin/frpc /app/proxy-client
RUN chmod +x /app/proxy-client

CMD ["/bin/bash"]