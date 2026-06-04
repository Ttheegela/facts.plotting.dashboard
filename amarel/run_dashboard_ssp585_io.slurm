#!/bin/bash
#SBATCH --job-name=facts-dash-io
#SBATCH --partition=kopp_1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/home/tt633/facts_dash_io_%j.out
#SBATCH --error=/home/tt633/facts_dash_io_%j.err

PYTHON="/home/tt633/miniconda3/bin/python"
SCRIPT="/scratch/tt633/facts_dashboard.py"
DATA="/scratch/tt633/facts-work/facts/exp.alt.emis/coupling.ssp585.io"
OUTPUT="/scratch/tt633/output"

export PYTHONPATH="/scratch/tt633/py_packages:${PYTHONPATH}"
mkdir -p "${OUTPUT}"

"${PYTHON}" "${SCRIPT}" \
  --ssp-dir "${DATA}" \
  --output "${OUTPUT}/amarel_ssp585_io.html" \
  --title "FACTS SSP585 — Indian Ocean 24 Tide Gauges (nsamps=2000)"

echo "Done. Output: ${OUTPUT}/amarel_ssp585_io.html"
