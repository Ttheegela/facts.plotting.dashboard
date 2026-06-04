#!/usr/bin/env bash
# Build the facts-viz Docker image for linux/amd64 (required for Amarel HPC).
# Use this instead of build.sh when targeting Rutgers Amarel or any x86_64 Linux HPC cluster.
#
# After building, convert to Singularity on Amarel — see amarel/AMAREL_SETUP.md

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building facts-viz-amd64 Docker image (linux/amd64)..."

# Copy facts_dashboard.py and requirements.txt into the build context
cp "${SCRIPT_DIR}/../facts_dashboard.py" "${SCRIPT_DIR}/facts_dashboard.py"
cp "${SCRIPT_DIR}/../requirements.txt" "${SCRIPT_DIR}/requirements.txt"

docker buildx build --platform linux/amd64 -t facts-viz-amd64 "${SCRIPT_DIR}"

# Clean up temp copies
rm "${SCRIPT_DIR}/facts_dashboard.py"
rm "${SCRIPT_DIR}/requirements.txt"

# Save as tarball for transfer to Amarel
OUTPUT_TAR="${SCRIPT_DIR}/../amarel/facts-viz-amd64.tar.gz"
mkdir -p "${SCRIPT_DIR}/../amarel"
echo ""
echo "Saving image as tarball → amarel/facts-viz-amd64.tar.gz ..."
docker save facts-viz-amd64 | gzip > "${OUTPUT_TAR}"

echo ""
echo "Done."
echo ""
echo "Next steps:"
echo "  1. Upload amarel/facts-viz-amd64.tar.gz to Amarel via OnDemand Files"
echo "  2. On Amarel shell:"
echo "       module load singularity"
echo "       singularity build /projects/kopp/facts-viz-amd64.sif docker-archive:///home/<your-netid>/facts-viz-amd64.tar.gz"
echo "  3. See amarel/AMAREL_SETUP.md for full run instructions"
