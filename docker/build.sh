#!/usr/bin/env bash
# Build the facts-viz Docker image.
# Run once, then use run.sh every time you want a dashboard.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building facts-viz Docker image..."

# Copy facts_dashboard.py and requirements.txt into the build context
cp "${SCRIPT_DIR}/../facts_dashboard.py" "${SCRIPT_DIR}/facts_dashboard.py"
cp "${SCRIPT_DIR}/../requirements.txt" "${SCRIPT_DIR}/requirements.txt"

docker build -t facts-viz "${SCRIPT_DIR}"

# Clean up temp copies
rm "${SCRIPT_DIR}/facts_dashboard.py"
rm "${SCRIPT_DIR}/requirements.txt"

echo ""
echo "Done. Image built: facts-viz"
echo ""
echo "To generate a dashboard, run:"
echo "  bash ${SCRIPT_DIR}/run.sh --exp-root /path/to/exp.alt.emis/"
echo "  bash ${SCRIPT_DIR}/run.sh --ssp-dir /path/to/coupling.ssp585/ --ssp-dir /path/to/coupling.ssp126/"
