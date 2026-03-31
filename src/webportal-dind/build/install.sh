#!/bin/bash


# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -eux

DOCKER_CHANNEL="stable"
DOCKER_VERSION="29.1.2"
DOCKER_COMPOSE_VERSION="v5.0.0"
BUILDX_VERSION="v0.30.1"

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
command=/usr/local/bin/dockerd --storage-driver=vfs --data-root=/var/lib/docker-vfs
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

log_info "Logging in to Docker registry"
DOCKER_REGISTRY=$(echo "$DOCKER_IMAGE" | cut -d'/' -f1)

# Get UAMI Client ID from Azure Workload Identity injected environment variable
if [ -z "$AZURE_CLIENT_ID" ]; then
    log_error "AZURE_CLIENT_ID environment variable not found"
    log_error "Please ensure azure-acr-identity service account is properly configured with Workload Identity"
    exit 1
fi

log_info "Using AZURE_CLIENT_ID: $AZURE_CLIENT_ID"

# For ACR authentication, we need to get a token for the ACR resource
IMDS_URL="http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/&client_id=${AZURE_CLIENT_ID}"

log_info "Getting AAD token from IMDS for ACR: ${DOCKER_REGISTRY}"
AAD_TOKEN=$(curl -s -H "Metadata: true" "${IMDS_URL}" | jq -r .access_token)
if [ "${AAD_TOKEN}" == "null" ] || [ -z "${AAD_TOKEN}" ]; then
    log_error "Failed to get AAD token from IMDS"
    exit 1
fi

log_info "Exchanging AAD token for ACR refresh token"
ACR_REFRESH_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=access_token&service=${DOCKER_REGISTRY}&access_token=${AAD_TOKEN}" \
    "https://${DOCKER_REGISTRY}/oauth2/exchange" | jq -r .refresh_token)
if [ "${ACR_REFRESH_TOKEN}" == "null" ] || [ -z "${ACR_REFRESH_TOKEN}" ]; then
    log_error "Failed to get ACR refresh token"
    exit 1
fi

log_info "Getting ACR access token"
# Extract full repository path (e.g., "luciaopenai/webportal" from "luciaopenpai.azurecr.io/luciaopenai/webportal:test")
DOCKER_REPOSITORY=$(echo "$DOCKER_IMAGE" | cut -d'/' -f2- | cut -d':' -f1)
log_info "Repository path: ${DOCKER_REPOSITORY}"
ACR_ACCESS_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=refresh_token&service=${DOCKER_REGISTRY}&scope=repository:${DOCKER_REPOSITORY}:pull&refresh_token=${ACR_REFRESH_TOKEN}" \
    "https://${DOCKER_REGISTRY}/oauth2/token" | jq -r .access_token)
if [ "${ACR_ACCESS_TOKEN}" == "null" ] || [ -z "${ACR_ACCESS_TOKEN}" ]; then
    log_error "Failed to get ACR access token"
    exit 1
fi

log_info "Logging in to Docker registry with ACR access token"
echo "${ACR_ACCESS_TOKEN}" | docker login "${DOCKER_REGISTRY}" \
    -u 00000000-0000-0000-0000-000000000000 \
    --password-stdin

log_info "Pulling webportal Docker image"
docker pull "$DOCKER_IMAGE":"$DOCKER_TAG"

docker run -d --name webportal \
    -e LAUNCHER_TYPE="$LAUNCHER_TYPE" \
    -e LAUNCHER_SCHEDULER="$LAUNCHER_SCHEDULER" \
    -e REST_SERVER_URI="$REST_SERVER_URI" \
    -e MARKETPLACE_API_URI="$MARKETPLACE_API_URI" \
    -e SAVE_TEMPLATE="$SAVE_TEMPLATE" \
    -e PROMETHEUS_URI="$PROMETHEUS_URI" \
    -e GRAFANA_URI="$GRAFANA_URI" \
    -e K8S_DASHBOARD_URI="$K8S_DASHBOARD_URI" \
    -e K8S_API_SERVER_URI="$K8S_API_SERVER_URI" \
    -e EXPORTER_PORT="$EXPORTER_PORT" \
    -e AUTHN_METHOD="$AUTHN_METHOD" \
    -e JOB_HISTORY="$JOB_HISTORY" \
    -e PROM_SCRAPE_TIME="$PROM_SCRAPE_TIME" \
    -e ENABLE_JOB_TRANSFER="$ENABLE_JOB_TRANSFER" \
    -e WEBPORTAL_PLUGINS="$WEBPORTAL_PLUGINS" \
    -p 8080:8080 \
    --memory=512m \
    -v /var/run/secrets/kubernetes.io/serviceaccount:/var/run/secrets/kubernetes.io/serviceaccount:ro \
    "$DOCKER_IMAGE":"$DOCKER_TAG"

EOF

chmod +x /usr/local/bin/start-docker.sh

