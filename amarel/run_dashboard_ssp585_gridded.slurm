#!/bin/bash
#SBATCH --job-name=facts-dash-grid
#SBATCH --partition=kopp_1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/home/tt633/facts_dash_grid_%j.out
#SBATCH --error=/home/tt633/facts_dash_grid_%j.err

PYTHON="/home/tt633/miniconda3/bin/python"
SCRIPT="/scratch/tt633/facts_dashboard.py"
DATA="/scratch/tt633/facts-work/facts/exp.alt.emis/coupling.ssp585.io.gridded"
OUTPUT="/scratch/tt633/output"

export PYTHONPATH="/scratch/tt633/py_packages:${PYTHONPATH}"
mkdir -p "${OUTPUT}"

"${PYTHON}" "${SCRIPT}" \
  --ssp-dir "${DATA}" \
  --output "${OUTPUT}/amarel_ssp585_gridded.html" \
  --title "FACTS SSP585 — Indian Ocean Basin Grid (8460 locations, nsamps=2000)"

echo "Done. Output: ${OUTPUT}/amarel_ssp585_gridded.html"
