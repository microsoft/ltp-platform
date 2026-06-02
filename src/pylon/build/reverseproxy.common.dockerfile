FROM golang:1.25.10 AS builder

RUN git clone --branch v0.68.1 --depth 1 https://github.com/fatedier/frp.git /frp
WORKDIR /frp

RUN go get github.com/go-jose/go-jose/v4@v4.1.4 && \
    go get github.com/quic-go/quic-go@v0.57.0 && \
    go get github.com/pion/dtls/v3@v3.0.11 && \
    go get github.com/Azure/go-ntlmssp@v0.1.1 && \
    go get golang.org/x/net@v0.55.0 && \
    go get golang.org/x/crypto@v0.52.0 && \
    go mod tidy && if [ -d vendor ]; then go work vendor 2>/dev/null || go mod vendor; fi

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