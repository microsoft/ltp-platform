FROM ubuntu:24.04

# Install required packages and clean up to reduce image size
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends openssh-server && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir /var/run/sshd

# Create a non-root user with home directory
RUN useradd -m -s /bin/bash sshuser

# Create SSH directory and set permissions
RUN mkdir -p /home/sshuser/.ssh && \
    chown sshuser:sshuser /home/sshuser/.ssh

# Expose SSH port
EXPOSE 22

# Set default command to run SSH daemon
CMD ["/usr/sbin/sshd", "-D"]