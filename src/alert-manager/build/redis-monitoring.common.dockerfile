# Redis with Built-in Monitoring Tools for Node Failure Detection
# Based on official Redis Alpine image with custom monitoring capabilities
FROM golang:1.24 AS gosu

WORKDIR /src

RUN git clone --branch 1.19 --depth 1 https://github.com/tianon/gosu.git .

RUN go mod edit -go=1.24 \
 && go mod edit -toolchain=go1.24.0 \
 && go mod tidy -compat=1.24

RUN go get -u ./... && go mod tidy -compat=1.24

RUN go mod download

RUN CGO_ENABLED=0 go build \
    -trimpath -buildvcs=false -ldflags="-s -w" \
    -o /usr/local/bin/gosu .

FROM redis:7-bullseye

# Metadata
LABEL maintainer="Alert Manager Team"
LABEL description="Redis with built-in monitoring tools for node-failure-detection"
LABEL version="1.0"

# Install additional tools needed for monitoring
# Note: Most tools (redis-cli, bash, date, ps, etc.) are already available in redis:7-alpine
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    bash \
    procps \
    curl \
    bc \
    vim \
    coreutils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# Create monitoring directory
RUN mkdir -p /opt/monitoring

# Copy monitoring scripts from src directory
COPY ./src/redis-monitoring/ /opt/monitoring/

# Make scripts executable
RUN chmod +x /opt/monitoring/*.sh

# Copy the gosu binary from the gosu stage
COPY --from=gosu /usr/local/bin/gosu /usr/local/bin/gosu

# Ensure it's executable
RUN chmod +x /usr/local/bin/gosu

# Add monitoring directory to PATH
ENV PATH="/opt/monitoring:${PATH}"


# Expose Redis port
EXPOSE 6379

# Set working directory
WORKDIR /data

CMD ["sh", "-c", "redis-server /etc/redis/redis.conf & /opt/monitoring/redis-watch.sh"]