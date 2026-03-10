#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# run.sh — Generate a FACTS sea-level projection dashboard
#
# Usage (all SSPs under one root):
#   bash run.sh --exp-root /path/to/exp.alt.emis/
#
# Usage (SSPs from separate runs):
#   bash run.sh \
#     --ssp-dir /run1/coupling.ssp126/ \
#     --ssp-dir /run2/coupling.ssp585/
#
# Optional flags (passed through to facts_dashboard.py):
#   --output /path/to/dashboard.html
#   --title  "My FACTS Run"
# ─────────────────────────────────────────────────────────

set -e

# ── Check Docker is available ────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed or not in PATH." >&2
    exit 1
fi

if ! docker image inspect facts-viz &>/dev/null; then
    echo "ERROR: facts-viz image not found."
    echo "       Run 'bash build.sh' first to build it."
    exit 1
fi

# ── Parse arguments to collect all paths that need mounting
# We scan for --exp-root, --ssp-dir, and --output values
# and auto-resolve them to absolute paths + mount them.
# ────────────────────────────────────────────────────────

MOUNTS=()        # -v host:container pairs
CONTAINER_ARGS=()  # args passed to facts_dashboard.py inside container

# Counter to give each mounted path a unique container path
MOUNT_IDX=0

resolve_and_mount() {
    local flag="$1"
    local host_path="$2"

    # Resolve to absolute path — handle the case where the parent dir may not
    # exist yet (e.g. --output pointing to a new file location).
    local host_dir_raw
    host_dir_raw="$(dirname "$host_path")"
    if [[ "$host_dir_raw" == "." ]]; then
        host_dir_raw="$(pwd)"
    fi
    local host_base
    host_base="$(basename "$host_path")"

    # Resolve the directory portion, creating it if it doesn't exist
    mkdir -p "$host_dir_raw" 2>/dev/null || true
    local host_dir_abs
    host_dir_abs="$(cd "$host_dir_raw" 2>/dev/null && pwd)" || host_dir_abs="$(pwd)"
    host_abs="${host_dir_abs}/${host_base}"

    # If it's a file path (--output flag or .html extension), mount the parent dir
    if [[ "$flag" == "--output" || "$host_path" == *.html || "$host_path" == *.htm ]]; then
        host_dir="$host_dir_abs"
        container_dir="/mnt/vol${MOUNT_IDX}"
        container_path="${container_dir}/${host_base}"
    else
        # It's a directory path: mount it directly
        host_dir="$host_abs"
        container_dir="/mnt/vol${MOUNT_IDX}"
        container_path="$container_dir"
    fi

    MOUNTS+=("-v" "${host_dir}:${container_dir}")
    CONTAINER_ARGS+=("$flag" "$container_path")
    MOUNT_IDX=$((MOUNT_IDX + 1))
}

# Walk through all arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exp-root|--ssp-dir|--output)
            resolve_and_mount "$1" "$2"
            shift 2
            ;;
        *)
            # Pass through any other flags (e.g. --title "My Run")
            CONTAINER_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#CONTAINER_ARGS[@]} -eq 0 ]]; then
    echo "Usage:"
    echo "  bash run.sh --exp-root /path/to/exp.alt.emis/"
    echo "  bash run.sh --ssp-dir /path/to/coupling.ssp126/ --ssp-dir /path/to/coupling.ssp585/"
    echo "  bash run.sh --exp-root /path/to/exp/ --output /path/to/dashboard.html --title 'My Run'"
    exit 1
fi

# ── Run the container ─────────────────────────────────────
echo "Running facts-viz container..."
echo ""

docker run --rm \
    "${MOUNTS[@]}" \
    facts-viz \
    "${CONTAINER_ARGS[@]}"
