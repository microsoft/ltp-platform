# Build stage
FROM golang:1.25.12 AS builder
WORKDIR /app

COPY ./src /app/model-proxy

RUN cd /app/model-proxy && go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -o /app/bin/modelproxy

# Final stage - static binary, alpine is sufficient
FROM alpine:3.21
WORKDIR /app

RUN apk upgrade --no-cache && apk add --no-cache ca-certificates

COPY --from=builder /app/bin/modelproxy /app/bin/modelproxy
