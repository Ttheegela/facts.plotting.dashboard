#!/usr/bin/env bash
# Build the facts-viz Docker image.
# Run once, then use run.sh every time you want a dashboard.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building facts-viz Docker image..."

# Copy facts_dashboard.py into the build context
cp "${SCRIPT_DIR}/../facts_dashboard.py" "${SCRIPT_DIR}/facts_dashboard.py"

docker build -t facts-viz "${SCRIPT_DIR}"

# Clean up temp copy
rm "${SCRIPT_DIR}/facts_dashboard.py"

echo ""
echo "Done. Image built: facts-viz"
echo ""
echo "To generate a dashboard, run:"
echo "  bash ${SCRIPT_DIR}/run.sh --exp-root /path/to/exp.alt.emis/"
echo "  bash ${SCRIPT_DIR}/run.sh --ssp-dir /path/to/coupling.ssp585/ --ssp-dir /path/to/coupling.ssp126/"
