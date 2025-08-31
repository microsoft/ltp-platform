FROM golang:1.25.0
WORKDIR /app

COPY ./src /app/model-proxy

RUN cd /app/model-proxy && go mod tidy && \
    go build -o /app/bin/modelproxy


