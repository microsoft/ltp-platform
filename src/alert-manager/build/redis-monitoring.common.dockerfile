# Redis with Built-in Monitoring Tools for Node Failure Detection
# Based on official Redis Alpine image with custom monitoring capabilities

FROM redis:7-bullseye

# Metadata
LABEL maintainer="Alert Manager Team"
LABEL description="Redis with built-in monitoring tools for node-failure-detection"
LABEL version="1.0"

# Install additional tools needed for monitoring
# Note: Most tools (redis-cli, bash, date, ps, etc.) are already available in redis:7-alpine
RUN apt-get update && apt-get install -y \
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


# Add monitoring directory to PATH
ENV PATH="/opt/monitoring:${PATH}"


# Expose Redis port
EXPOSE 6379

# Set working directory
WORKDIR /data

CMD ["sh", "-c", "redis-server /etc/redis/redis.conf & /opt/monitoring/redis-watch.sh"]