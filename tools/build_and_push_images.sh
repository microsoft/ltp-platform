#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GIT_DIR="$(git -C "$REPO_ROOT" rev-parse --git-dir)"
if [[ "$GIT_DIR" != /* ]]; then
    GIT_DIR="$REPO_ROOT/$GIT_DIR"
fi
PROGRESS_DIR="$GIT_DIR/ltp-image-tools"

CONFIG_DIR=""
ACTION=""
START_FROM=0
RESET=false
SHOW_STATUS=false
LIST_TASKS=false
NO_CACHE=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# These images are intentionally not part of the maintained-image workflow.
EXCLUDED_SERVICES=(
    "base-image"
    "dev-box"
    "internal-storage"
)
EXCLUDED_IMAGES=(
    "cleaning-image/cleaning-image"
    "k8s-dashboard/kubernetes-dashboard-amd64"
    "marketplace-db/marketplace-db"
    "postgresql-sdk/postgresql-sdk"
    "prometheus-pushgateway/prometheus-pushgateway"
    "prometheus/prometheus"
)

TASKS=()

usage() {
    cat <<EOF
Usage: $0 <build|push|all> -c <config_dir> [OPTIONS]

Actions:
  build            Build all maintained images
  push             Push all maintained images
  all              Build all images, then push them

Options:
  -c, --config DIR Configuration directory for pai_build.py
  --reset          Clear progress for the selected action
  --from N         Start from step N and ignore earlier progress
  --status         Show progress without running
  --list           List discovered image tasks
  --use-cache      Allow Docker build cache (builds use --nocache by default)
  -h, --help       Show this help

Progress is stored under .git/ltp-image-tools so it does not dirty the worktree.
Cilium pushes use src/cilium/build/push.sh because their tags differ from the
standard pai_build.py push flow.
EOF
}

is_excluded_service() {
    local candidate=$1
    local excluded
    for excluded in "${EXCLUDED_SERVICES[@]}"; do
        if [[ "$candidate" == "$excluded" ]]; then
            return 0
        fi
    done
    return 1
}

is_excluded_image() {
    local candidate=$1
    local excluded
    for excluded in "${EXCLUDED_IMAGES[@]}"; do
        if [[ "$candidate" == "$excluded" ]]; then
            return 0
        fi
    done
    return 1
}

discover_tasks() {
    local dockerfile relative service filename image key
    while IFS= read -r dockerfile; do
        relative="${dockerfile#"$REPO_ROOT/src/"}"
        service="${relative%%/*}"
        if is_excluded_service "$service"; then
            continue
        fi

        filename="${dockerfile##*/}"
        image="${filename%.common.dockerfile}"
        image="${image%.k8s.dockerfile}"
        key="$(task_key "$service" "$image")"
        if is_excluded_image "$key"; then
            continue
        fi
        TASKS+=("$service|$image")
    done < <(
        find "$REPO_ROOT/src" -mindepth 3 -maxdepth 3 -type f \
            \( -name '*.common.dockerfile' -o -name '*.k8s.dockerfile' \) \
            -path '*/build/*' | LC_ALL=C sort
    )

    if [[ ${#TASKS[@]} -eq 0 ]]; then
        echo -e "${RED}Error: no image Dockerfiles were discovered.${NC}" >&2
        exit 1
    fi
}

progress_file() {
    echo "$PROGRESS_DIR/$1.progress"
}

task_key() {
    local service=$1
    local image=$2
    echo "$service/$image"
}

is_completed() {
    local phase=$1
    local key=$2
    local file
    file="$(progress_file "$phase")"
    [[ -f "$file" ]] && grep -Fqx "$key" "$file"
}

mark_completed() {
    local phase=$1
    local key=$2
    local file
    file="$(progress_file "$phase")"
    mkdir -p "$PROGRESS_DIR"
    if ! is_completed "$phase" "$key"; then
        echo "$key" >> "$file"
    fi
}

mark_cilium_push_completed() {
    local task service image
    for task in "${TASKS[@]}"; do
        IFS='|' read -r service image <<< "$task"
        if [[ "$service" == "cilium" ]]; then
            mark_completed push "$(task_key "$service" "$image")"
        fi
    done
}

show_phase_status() {
    local phase=$1
    local completed=0
    local step=0
    local task service image key state color

    echo -e "${BLUE}=== ${phase^} Progress ===${NC}"
    for task in "${TASKS[@]}"; do
        step=$((step + 1))
        IFS='|' read -r service image <<< "$task"
        key="$(task_key "$service" "$image")"
        if is_completed "$phase" "$key"; then
            completed=$((completed + 1))
            state="DONE"
            color="$GREEN"
        else
            state="TODO"
            color="$YELLOW"
        fi
        echo -e "  ${color}[${state}]${NC} Step ${step}: ${key}"
    done
    echo -e "Completed: ${GREEN}${completed}${NC} / ${#TASKS[@]}"
}

list_all_tasks() {
    local step=0
    local task service image
    echo "=== Discovered Image Tasks ==="
    for task in "${TASKS[@]}"; do
        step=$((step + 1))
        IFS='|' read -r service image <<< "$task"
        echo "  Step ${step}: ${service}/${image}"
    done
    echo "Total: ${#TASKS[@]}"
    echo "Excluded services: ${EXCLUDED_SERVICES[*]}"
    echo "Excluded images: ${EXCLUDED_IMAGES[*]}"
}

run_build() {
    local service=$1
    local image=$2
    local command=(
        "$REPO_ROOT/build/pai_build.py"
        build
        -c "$CONFIG_DIR"
        -s "$service"
        -i "$image"
    )
    if [[ "$NO_CACHE" == true ]]; then
        command+=(--nocache)
    fi
    "${command[@]}"
}

run_push() {
    local service=$1
    local image=$2
    if [[ "$service" == "cilium" ]]; then
        "$REPO_ROOT/src/cilium/build/push.sh" -c "$CONFIG_DIR"
    else
        "$REPO_ROOT/build/pai_build.py" push -c "$CONFIG_DIR" -i "$image"
    fi
}

run_phase() {
    local phase=$1
    local step=0
    local completed=0
    local skipped=0
    local failed=0
    local cilium_pushed=false
    local task service image key

    echo -e "${BLUE}=== ${phase^}ing All Maintained Images ===${NC}"
    echo "Discovered images: ${#TASKS[@]}"
    echo ""

    for task in "${TASKS[@]}"; do
        step=$((step + 1))
        IFS='|' read -r service image <<< "$task"
        key="$(task_key "$service" "$image")"

        if [[ $START_FROM -gt 0 && $step -lt $START_FROM ]]; then
            skipped=$((skipped + 1))
            continue
        fi

        if [[ $START_FROM -eq 0 ]] && is_completed "$phase" "$key"; then
            echo -e "  ${GREEN}[SKIP]${NC} Step ${step}/${#TASKS[@]}: ${key} (already done)"
            skipped=$((skipped + 1))
            continue
        fi

        if [[ "$phase" == "push" && "$service" == "cilium" && "$cilium_pushed" == true ]]; then
            skipped=$((skipped + 1))
            continue
        fi

        echo -e "${BLUE}[${phase^^}]${NC} Step ${step}/${#TASKS[@]}: ${key}"
        if [[ "$phase" == "build" ]]; then
            if run_build "$service" "$image"; then
                mark_completed "$phase" "$key"
                completed=$((completed + 1))
            else
                failed=1
            fi
        else
            if run_push "$service" "$image"; then
                if [[ "$service" == "cilium" ]]; then
                    mark_cilium_push_completed
                    cilium_pushed=true
                else
                    mark_completed "$phase" "$key"
                fi
                completed=$((completed + 1))
            else
                failed=1
            fi
        fi

        if [[ $failed -ne 0 ]]; then
            echo -e "  ${RED}[FAIL]${NC} Step ${step}/${#TASKS[@]}: ${key}"
            echo "Resume after fixing the issue by rerunning the same command."
            break
        fi
        echo -e "  ${GREEN}[OK]${NC} Step ${step}/${#TASKS[@]}: ${key}"
    done

    echo ""
    echo -e "${BLUE}=== ${phase^} Summary ===${NC}"
    echo -e "  Completed: ${GREEN}${completed}${NC}"
    echo -e "  Skipped:   ${YELLOW}${skipped}${NC}"
    echo -e "  Failed:    ${RED}${failed}${NC}"
    return "$failed"
}

if [[ $# -gt 0 && "$1" != -* ]]; then
    ACTION=$1
    shift
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a directory." >&2
                exit 1
            fi
            CONFIG_DIR=$2
            shift 2
            ;;
        --reset)
            RESET=true
            shift
            ;;
        --from)
            if [[ $# -lt 2 || ! "$2" =~ ^[1-9][0-9]*$ ]]; then
                echo "Error: --from requires a positive step number." >&2
                exit 1
            fi
            START_FROM=$2
            shift 2
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --list)
            LIST_TASKS=true
            shift
            ;;
        --use-cache)
            NO_CACHE=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

case "$ACTION" in
    build|push|all) ;;
    *)
        echo "Error: action must be build, push, or all." >&2
        usage >&2
        exit 1
        ;;
esac

discover_tasks

if [[ "$LIST_TASKS" == true ]]; then
    list_all_tasks
    exit 0
fi

if [[ "$SHOW_STATUS" == true ]]; then
    if [[ "$ACTION" == "build" || "$ACTION" == "all" ]]; then
        show_phase_status build
    fi
    if [[ "$ACTION" == "push" || "$ACTION" == "all" ]]; then
        show_phase_status push
    fi
    exit 0
fi

if [[ -z "$CONFIG_DIR" ]]; then
    echo -e "${RED}Error: -c <config_dir> is required.${NC}" >&2
    exit 1
fi
if [[ ! -f "$CONFIG_DIR/services-configuration.yaml" ]]; then
    echo -e "${RED}Error: $CONFIG_DIR/services-configuration.yaml does not exist.${NC}" >&2
    exit 1
fi
CONFIG_DIR="$(cd "$CONFIG_DIR" && pwd)"

if [[ "$RESET" == true ]]; then
    mkdir -p "$PROGRESS_DIR"
    if [[ "$ACTION" == "build" || "$ACTION" == "all" ]]; then
        rm -f "$(progress_file build)"
    fi
    if [[ "$ACTION" == "push" || "$ACTION" == "all" ]]; then
        rm -f "$(progress_file push)"
    fi
fi

cd "$REPO_ROOT"
if [[ "$ACTION" == "build" || "$ACTION" == "all" ]]; then
    run_phase build
fi
if [[ "$ACTION" == "push" || "$ACTION" == "all" ]]; then
    run_phase push
fi
