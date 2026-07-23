#!/bin/bash
# Push cilium images with correct version tags to ACR.
# Reads registry domain from pai config and versions from Dockerfiles.
# Local images are expected to be built as:
#   cilium-agent:latest, cilium-operator:latest, cilium-envoy:latest
#
# Usage: ./push.sh -c <config_dir> [-n <namespace>]
#   e.g.: ./push.sh -c ~/configs/config-auto
#   e.g.: ./push.sh -c ~/configs/config-auto -n @config
#   e.g.: ./push.sh -c ~/configs/config-auto -n my-namespace
#
# Options:
#   -c <config_dir>   Path to pai config directory (required)
#   -n <namespace>    Image namespace (default: cilium)
#                     Use "@config" to read namespace from services-configuration.yaml
#   -h                Show this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 -c <config_dir> [-n <namespace>]"
    echo ""
    echo "Push cilium images to ACR with version-based tags."
    echo "Expects local images: cilium-agent:latest, cilium-operator:latest, cilium-envoy:latest"
    echo ""
    echo "Options:"
    echo "  -c <config_dir>   Path to pai config directory (required)"
    echo "  -n <namespace>    Image namespace (default: cilium)"
    echo "                    Use \"@config\" to read namespace from services-configuration.yaml"
    echo "  -h                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -c ~/configs/config-auto"
    echo "  $0 -c ~/configs/config-auto -n @config"
    echo "  $0 -c ~/configs/config-auto -n my-namespace"
}

# Parse arguments
CONFIG_DIR=""
NAMESPACE="cilium"

while getopts "c:n:h" opt; do
    case $opt in
        c) CONFIG_DIR="$OPTARG" ;;
        n) NAMESPACE="$OPTARG" ;;
        h) usage; exit 0 ;;
        *) usage; exit 1 ;;
    esac
done

if [ -z "$CONFIG_DIR" ]; then
    usage
    exit 1
fi

SERVICES_CONFIG="$CONFIG_DIR/services-configuration.yaml"
if [ ! -f "$SERVICES_CONFIG" ]; then
    echo "Error: $SERVICES_CONFIG not found"
    exit 1
fi

# Parse registry info from services-configuration.yaml using python/yaml
read_config_value() {
    python3 -c "
import yaml
with open('$SERVICES_CONFIG') as f:
    cfg = yaml.safe_load(f)
val = cfg
for key in '$1'.split('.'):
    val = val[key]
print(val)
"
}

REGISTRY=$(read_config_value "cluster.docker-registry.domain")
if [ -z "$REGISTRY" ]; then
    echo "Error: could not parse docker-registry.domain from $SERVICES_CONFIG"
    exit 1
fi

# Resolve namespace
if [ "$NAMESPACE" = "@config" ]; then
    NAMESPACE=$(read_config_value "cluster.docker-registry.namespace")
    if [ -z "$NAMESPACE" ]; then
        echo "Error: could not parse docker-registry.namespace from $SERVICES_CONFIG"
        exit 1
    fi
    echo "Namespace read from config: $NAMESPACE"
fi

# Parse versions from Dockerfiles
CILIUM_VERSION=$(grep -m1 'ARG CILIUM_VERSION=' "$SCRIPT_DIR/cilium-agent.common.dockerfile" | cut -d= -f2)
ENVOY_TAG=$(grep -m1 'ARG CILIUM_ENVOY_TAG=' "$SCRIPT_DIR/cilium-envoy.common.dockerfile" | cut -d= -f2)
ENVOY_VERSION=$(echo "$ENVOY_TAG" | sed 's/-[a-f0-9]\{40\}$//')

echo ""
echo "Registry:  $REGISTRY"
echo "Namespace: $NAMESPACE"
echo "Cilium:    $CILIUM_VERSION"
echo "Envoy:     $ENVOY_VERSION"
echo ""

# Login to ACR
REGISTRY_NAME="${REGISTRY%.azurecr.io}"
echo "Logging in to ACR: $REGISTRY_NAME ..."
if ! az acr login --name "$REGISTRY_NAME"; then
    echo "Error: failed to login to ACR '$REGISTRY_NAME'. Please check your Azure credentials."
    exit 1
fi
echo ""

# Map: local_image -> remote_image
declare -A IMAGE_MAP=(
    ["cilium-agent:latest"]="${NAMESPACE}/cilium:${CILIUM_VERSION}-update"
    ["cilium-operator:latest"]="${NAMESPACE}/operator-generic:${CILIUM_VERSION}-update"
    ["cilium-envoy:latest"]="${NAMESPACE}/cilium-envoy:${ENVOY_VERSION}-update"
)

FAILED=0
for local_img in "${!IMAGE_MAP[@]}"; do
    remote_img="${REGISTRY}/${IMAGE_MAP[$local_img]}"
    if ! docker image inspect "$local_img" &>/dev/null; then
        echo "Skipping ${local_img} (not found locally)"
        echo ""
        continue
    fi
    echo "Tagging ${local_img} -> ${remote_img}"
    docker tag "$local_img" "$remote_img"
    echo "Pushing ${remote_img} ..."
    if ! docker push "$remote_img"; then
        echo "Error: failed to push ${remote_img}"
        FAILED=1
    fi
    echo ""
done

if [ "$FAILED" -ne 0 ]; then
    echo "Warning: some images failed to push."
    exit 1
fi

echo "Done."
