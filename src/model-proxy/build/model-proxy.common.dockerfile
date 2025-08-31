FROM golang:1.25.0
WORKDIR /app

COPY . .

RUN go mod tidy && \
    go build -o /app/bin/modelproxy

