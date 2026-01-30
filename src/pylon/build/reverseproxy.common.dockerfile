FROM golang:1.24 AS builder

RUN git clone --branch v0.66.0 --depth 1 https://github.com/fatedier/frp.git /frp
WORKDIR /frp

RUN go get github.com/quic-go/quic-go@v0.57.0 && \
    go get golang.org/x/crypto@v0.45.0 && \
    go mod tidy

RUN make frpc

FROM ubuntu:22.04

# Set up working directory
WORKDIR /app

# Install dependencies if needed (e.g., curl for debugging)
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get -y install bash curl

# Install Python dependencies
RUN apt-get -y install build-essential python3 python3-pip
RUN pip3 install jinja2

COPY --from=builder /frp/bin/frpc /app/proxy-client
RUN chmod +x /app/proxy-client

# Ensure the binary is executable
RUN chmod +x /app/proxy-client

CMD ["/bin/bash"]