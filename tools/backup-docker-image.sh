
#!/usr/bin/env bash
set -euo pipefail

# -------------------------------
# Usage (two styles supported)
# 1) Positional arguments:
#    ./backup-docker-image.sh <acr_name> <backup_tag>
#    e.g.: ./backup-docker-image.sh contoso golden-2026-0101
#
# 2) Option flags:
#    ./backup-docker-image.sh -r <acr_name> -t <backup_tag>
#    e.g.: ./backup-docker-image.sh -r contoso -t golden-2026-0101
#
# Optional:
#    -y/--yes        non-interactive confirmation
#    -h/--help       show help
# -------------------------------

ACR_NAME=""
BACKUP_TAG=""
ASSUME_YES="false"

# -------------------------------
# Emoji theme (customizable)
# -------------------------------
EMO_INFO="ℹ️"
EMO_WARN="⚠️"
EMO_ERROR="❌"
EMO_SKIP="⏭️"
EMO_OK="✅"
EMO_RUN="🚀"
EMO_FIND="🔎"
EMO_TAG="🏷️"

print_help() {
  cat <<'EOF'
Usage:
  backup-docker-image.sh <acr_name> <backup_tag>
  backup-docker-image.sh -r <acr_name> -t <backup_tag> [-y]

Options:
  -r, --registry   ACR name (without domain, e.g., contoso)
  -t, --tag        backup tag name (e.g., golden-2026-0101)
  -y, --yes        non-interactive confirmation, skip prompt
  -h, --help       show help

Examples:
  ./backup-docker-image.sh contoso golden-2026-0101
  ./backup-docker-image.sh -r contoso -t golden-2026-0101 -y
EOF
}

# Support positional args
if [[ $# -ge 2 && "$1" != "-"* && "$2" != "-"* ]]; then
  ACR_NAME="$1"
  BACKUP_TAG="$2"
  shift 2
fi

# Parse options
while [[ $# -gt 0 ]]; do
  case "$1" in
    -r|--registry)
      ACR_NAME="${2:-}"; shift 2 ;;
    -t|--tag)
      BACKUP_TAG="${2:-}"; shift 2 ;;
    -y|--yes)
      ASSUME_YES="true"; shift ;;
    -h|--help)
      print_help; exit 0 ;;
    *)
      echo "$EMO_ERROR  Unknown option: $1"; print_help; exit 1 ;;
  esac
done

# Required checks
if [[ -z "$ACR_NAME" || -z "$BACKUP_TAG" ]]; then
  echo "$EMO_ERROR  ACR name and backup tag are required."
  print_help
  exit 1
fi

# Basic format checks
if [[ "$ACR_NAME" =~ [A-Z] ]]; then
  echo "$EMO_WARN  ACR name contains uppercase letters. Azure ACR names are typically lowercase (e.g., contoso)."
fi
if [[ "$BACKUP_TAG" =~ [[:space:]] ]]; then
  echo "$EMO_ERROR  Backup tag must not contain whitespace."
  exit 1
fi

echo "$EMO_INFO  Target ACR: $ACR_NAME"
echo "$EMO_TAG  Backup tag: $BACKUP_TAG"

# Get login server (e.g., contoso.azurecr.io)
REGISTRY_FQDN="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"

# Confirmation prompt
if [[ "$ASSUME_YES" != "true" ]]; then
  read -r -p "$EMO_RUN  This will add tag '$BACKUP_TAG' to **all repositories that have 'latest'** in '$ACR_NAME'. Continue? [y/N] " ans
  if [[ ! "$ans" =~ ^[Yy]$ ]]; then
    echo "$EMO_SKIP  Cancelled."
    exit 0
  fi
fi

# Main loop: import (latest -> BACKUP_TAG) for each repository
set -o pipefail
echo "$EMO_FIND  Listing repositories ..."
az acr repository list -n "$ACR_NAME" -o tsv | while read -r REPO; do
  # Exact match for 'latest'
  if az acr repository show-tags -n "$ACR_NAME" --repository "$REPO" -o tsv | grep -qx "latest"; then
    echo "$EMO_INFO  $REPO has 'latest'. Adding tag '$BACKUP_TAG' ..."
    az acr import \
      -n "$ACR_NAME" \
      --source "$REGISTRY_FQDN/$REPO:latest" \
      -t "$REPO:$BACKUP_TAG" \
      --force
  else
    echo "$EMO_SKIP  $REPO does not have 'latest'. Skipping."
  fi
done

echo "$EMO_OK  Done: Added tag '$BACKUP_TAG' to all repositories that have 'latest'."
