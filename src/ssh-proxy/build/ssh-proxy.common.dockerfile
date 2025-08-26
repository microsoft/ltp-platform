FROM ubuntu:24.04

# Install required packages and clean up to reduce image size
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends openssh-server && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir /var/run/sshd

# Create a non-root user with home directory
RUN useradd -m -s /bin/bash azureuser

# Create SSH directory and set permissions
RUN mkdir -p /home/azureuser/.ssh && \
    chown azureuser:azureuser /home/azureuser/.ssh

# Expose SSH port
EXPOSE 22

# Set default command to run SSH daemon
CMD ["/usr/sbin/sshd", "-D"]