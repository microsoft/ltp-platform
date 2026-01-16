# Build stage
FROM golang:1.25.5 AS builder
WORKDIR /app

COPY ./src /app/model-proxy

RUN cd /app/model-proxy && go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -o /app/bin/modelproxy

# Final stage
FROM ubuntu:latest
WORKDIR /app

RUN apt-get update

RUN apt-get upgrade -y

COPY --from=builder /app/bin/modelproxy /app/bin/modelproxy
