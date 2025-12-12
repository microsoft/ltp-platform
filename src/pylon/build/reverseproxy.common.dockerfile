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

ENV FRP_VERSION=0.65.0
# Download the binary from its GitHub releases
RUN curl -L -o proxy.tar.gz https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz && \
    tar -zxvf proxy.tar.gz --strip-components=1 -C /app && \
    mv frpc proxy-client && \
    rm proxy.tar.gz && \
    rm frp*

# Ensure the binary is executable
RUN chmod +x /app/proxy-client


CMD ["/bin/bash"]