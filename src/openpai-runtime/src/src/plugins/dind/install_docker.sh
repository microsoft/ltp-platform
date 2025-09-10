#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -eux

DOCKER_CHANNEL="stable"
DOCKER_VERSION="28.2.2"
DOCKER_COMPOSE_VERSION="v2.37.1"
BUILDX_VERSION="v0.24.0"

# Logging functions
function log_info() {
    echo "[INFO] $1"
}

function log_error() {
    echo "[ERROR] $1"
}

# Check ubuntu version
UBUNTU_VERSION=$(grep '^VERSION_ID=' /etc/os-release | cut -d '"' -f2)
if [[ -z "$UBUNTU_VERSION" ]]; then
  echo "Unable to determine Ubuntu version. Please ensure lsb_release is installed." >&2
  exit 1
fi

# === Install dependencies ===
apt-get update
apt-get install -y \
  ca-certificates wget curl iptables supervisor gnupg sudo

# === Set iptables-legacy if needed ===
if [[ "$UBUNTU_VERSION" != "20.04" ]]; then
  update-alternatives --set iptables /usr/sbin/iptables-legacy
fi

# === Install Docker + buildx ===
arch="$(uname -m)"
case "$arch" in
  x86_64) dockerArch='x86_64'; buildx_arch='linux-amd64' ;;
  armhf)  dockerArch='armel'; buildx_arch='linux-arm-v6' ;;
  armv7)  dockerArch='armhf'; buildx_arch='linux-arm-v7' ;;
  aarch64) dockerArch='aarch64'; buildx_arch='linux-arm64' ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac

wget -O docker.tgz "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/${dockerArch}/docker-${DOCKER_VERSION}.tgz"
tar --extract --file docker.tgz --strip-components 1 --directory /usr/local/bin/
rm docker.tgz

wget -O docker-buildx "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.${buildx_arch}"
mkdir -p /usr/local/lib/docker/cli-plugins
chmod +x docker-buildx
mv docker-buildx /usr/local/lib/docker/cli-plugins/docker-buildx

# === Install Docker Compose ===
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -s /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /var/lib/docker

# -------------------------------
# Create modprobe shim
# -------------------------------
cat << 'EOF' > /usr/local/bin/modprobe
#!/bin/sh
set -eu
# "modprobe" without modprobe
# https://twitter.com/lucabruno/status/902934379835662336
# Docker often uses "modprobe -va foo bar baz"
# so we ignore modules that start with "-"
for module; do
	if [ "${module#-}" = "$module" ]; then
		ip link show "$module" || true
		lsmod | grep "$module" || true
	fi
done

# remove /usr/local/... from PATH so we can exec the real modprobe as a last resort
export PATH='/usr/sbin:/usr/bin:/sbin:/bin'
exec modprobe "$@"
EOF

chmod +x /usr/local/bin/modprobe

# === Supervisor configuration ===
mkdir -p /etc/supervisor/conf.d
cat <<EOF > /etc/supervisor/conf.d/dockerd.conf
[program:dockerd]
command=/usr/local/bin/dockerd
autostart=true
autorestart=true
stderr_logfile=/var/log/dockerd.err.log
stdout_logfile=/var/log/dockerd.out.log
EOF


# === start-docker.sh script ===
cat << 'EOF' > /usr/local/bin/start-docker.sh
#!/bin/bash

function log_info() {
    echo "[INFO] $1"
}

function log_error() {
    echo "[ERROR] $1"
}

function wait_for_process () {
    local max_time_wait=30
    local process_name="$1"
    local waited_sec=0
    while ! pgrep "$process_name" >/dev/null && ((waited_sec < max_time_wait)); do
        log_info "Process $process_name is not running yet. Retrying in 1 seconds"
        log_info "Waited $waited_sec seconds of $max_time_wait seconds"
        sleep 1
        ((waited_sec=waited_sec+1))
        if ((waited_sec >= max_time_wait)); then
            return 1
        fi
    done
    return 0
}

log_info "Starting supervisor"
/usr/bin/supervisord -n >> /dev/null 2>&1 &

log_info "Waiting for docker to be running"
wait_for_process dockerd
if [ $? -ne 0 ]; then
    log_error "dockerd is not running after max time"
    exit 1
else
    log_info "dockerd is running"
fi
EOF

chmod +x /usr/local/bin/start-docker.sh

# check if NVIDIA GPU is available
if command -v nvidia-smi >/dev/null 2>&1; then
    log_info "NVIDIA GPU detected. Installing NVIDIA Container Toolkit."
    # === NVIDIA Container Toolkit ===
    # Download and install GPG key
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    
    # Add NVIDIA repository
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    apt-get update
    export NVIDIA_CONTAINER_TOOLKIT_VERSION=1.17.8-1
    apt-get install -y \
        nvidia-container-toolkit=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        nvidia-container-toolkit-base=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        libnvidia-container-tools=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        libnvidia-container1=${NVIDIA_CONTAINER_TOOLKIT_VERSION}
    nvidia-ctk runtime configure --runtime=docker
else
    log_info "No NVIDIA GPU detected. Skipping NVIDIA Container Toolkit installation."
fi

# === Enable Docker service ===
bash /usr/local/bin/start-docker.sh

# === Validate ===
docker info || {
    echo "Docker installation failed. Please check the logs." >&2
    exit 1
}

echo "Setup complete."
