#!/usr/bin/env bash
set -euo pipefail

# Development-only platform data reset.
#
# This intentionally purges disposable platform data while preserving service
# configuration and deployment files. It is not a production evidence-retention
# or factory-reset mechanism.
#
# Current shared data roots:
#   /data/services/recordings
#   /data/services/logs
#   /data/services/metadata
#   /data/services/state
#
# The reset also truncates Docker JSON log files for containers whose names
# begin with "edge-".
#
# Usage:
#   sudo ./reset-node-data.sh --all
#   sudo ./reset-node-data.sh --all --yes
#   sudo ./reset-node-data.sh --all --dry-run

DATA_ROOT="${EDGE_SERVICES_ROOT:-/data/services}"
MODE=""
ASSUME_YES=false
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage:
  reset-node-data.sh --all [--yes] [--dry-run]

Options:
  --all       Purge all currently-defined disposable platform data on this node.
  --yes       Skip the interactive destructive-operation confirmation.
  --dry-run   Show what would be stopped/purged without changing anything.
  -h, --help  Show this help.

Current behavior:
  - Stops currently running Docker containers named edge-*.
  - Purges recordings, logs, metadata, and edge-time/service state under
    EDGE_SERVICES_ROOT (default: /data/services).
  - Truncates Docker container log files for edge-* containers.
  - Restarts containers that were running before the reset.
  - Preserves configuration and deployment files.

This is a development reset, not a production evidence-deletion mechanism.
Service-specific purge and controller/GUI management are future capabilities.
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            MODE="all"
            ;;
        --yes)
            ASSUME_YES=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            die "Unknown argument: $1"
            ;;
    esac
    shift
done

[[ "$MODE" == "all" ]] || {
    usage >&2
    die "A reset scope is required. Currently supported scope: --all"
}

[[ -n "$DATA_ROOT" ]] || die "EDGE_SERVICES_ROOT is empty."
[[ "$DATA_ROOT" = /* ]] || die "EDGE_SERVICES_ROOT must be an absolute path."
[[ "$DATA_ROOT" != "/" ]] || die "Refusing to operate on /."
[[ "$DATA_ROOT" != "/data" ]] || die "Refusing to operate on /data."

command -v docker >/dev/null 2>&1 || die "docker is required."
[[ -d "$DATA_ROOT" ]] || die "Data root does not exist: $DATA_ROOT"

if [[ "$DRY_RUN" == false && "$ASSUME_YES" == false ]]; then
    echo
    echo "WARNING: This will permanently delete disposable platform data on this node."
    echo
    echo "Data root: $DATA_ROOT"
    echo
    echo "The following will be purged:"
    printf '  - %s\n' \
        "$DATA_ROOT/recordings" \
        "$DATA_ROOT/logs" \
        "$DATA_ROOT/metadata" \
        "$DATA_ROOT/state"
    echo
    read -r -p 'Type RESET to continue: ' confirmation
    [[ "$confirmation" == "RESET" ]] || {
        echo "Reset cancelled."
        exit 0
    }
fi

running_containers="$(docker ps --format '{{.Names}}' | awk '/^edge-/')"
edge_containers="$(docker ps -a --format '{{.Names}}' | awk '/^edge-/')"

running_count=0
edge_count=0
[[ -z "$running_containers" ]] || running_count="$(printf '%s\n' "$running_containers" | grep -c . || true)"
[[ -z "$edge_containers" ]] || edge_count="$(printf '%s\n' "$edge_containers" | grep -c . || true)"

echo "Development node reset"
echo "  data root: $DATA_ROOT"
echo "  running edge containers: $running_count"
echo "  edge containers found:   $edge_count"

if [[ "$DRY_RUN" == true ]]; then
    echo
    echo "DRY RUN - containers that would be stopped:"
    if [[ -z "$running_containers" ]]; then
        echo "  none"
    else
        printf '  %s\n' "$running_containers"
    fi

    echo
    echo "DRY RUN - data roots that would be purged:"
    for path in "$DATA_ROOT/recordings" "$DATA_ROOT/logs" "$DATA_ROOT/metadata" "$DATA_ROOT/state"; do
        if [[ -e "$path" ]]; then
            echo "  PURGE $path"
        else
            echo "  SKIP  $path (not present)"
        fi
    done

    echo
    echo "DRY RUN - Docker logs that would be truncated:"
    if [[ -z "$edge_containers" ]]; then
        echo "  none"
    else
        while IFS= read -r name; do
            [[ -n "$name" ]] || continue
            log_path="$(docker inspect --format '{{.LogPath}}' "$name" 2>/dev/null || true)"
            if [[ -n "$log_path" && "$log_path" != "<no value>" ]]; then
                echo "  $name -> $log_path"
            else
                echo "  $name -> no Docker log path"
            fi
        done <<< "$edge_containers"
    fi

    exit 0
fi

echo
echo "Stopping running edge containers..."
if [[ -n "$running_containers" ]]; then
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        echo "  stop $name"
        docker stop "$name" >/dev/null
    done <<< "$running_containers"
fi

echo
echo "Purging disposable platform data..."
for path in "$DATA_ROOT/recordings" "$DATA_ROOT/logs" "$DATA_ROOT/metadata" "$DATA_ROOT/state"; do
    if [[ -e "$path" ]]; then
        echo "  purge $path"
        rm -rf -- "$path"
        mkdir -p -- "$path"
    else
        echo "  create $path"
        mkdir -p -- "$path"
    fi
done

# edge-time runs as UID/GID 1000 in the current deployment.
# Keep the freshly-created shared state directory writable by that service.
chown 1000:1000 "$DATA_ROOT/state"
chmod 700 "$DATA_ROOT/state"

echo
echo "Truncating Docker logs..."
if [[ -n "$edge_containers" ]]; then
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        log_path="$(docker inspect --format '{{.LogPath}}' "$name" 2>/dev/null || true)"

        if [[ -n "$log_path" && "$log_path" != "<no value>" && -f "$log_path" ]]; then
            echo "  truncate $name -> $log_path"
            : > "$log_path"
        else
            echo "  skip $name (no Docker log file)"
        fi
    done <<< "$edge_containers"
fi

echo
echo "Restarting containers that were running before the reset..."
if [[ -n "$running_containers" ]]; then
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        echo "  start $name"
        docker start "$name" >/dev/null
    done <<< "$running_containers"
fi

echo
echo "Reset complete."
echo "Configuration and deployment files were not targeted."