#!/bin/bash
#SBATCH --job-name=facts-dashboard
#SBATCH --partition=main
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/home/%u/facts_dashboard_%j.out
#SBATCH --error=/home/%u/facts_dashboard_%j.err

# ── Configure these paths before submitting ───────────────────────────────────
SIF_PATH="/projects/kopp/tt633/singularity/facts-viz-amd64.sif"
DATA_PATH="/path/to/your/exp.alt.emis"       # absolute path to FACTS output on Amarel
OUTPUT_PATH="/scratch/<your-netid>/output"   # where to save the HTML (use scratch for large runs)
# ──────────────────────────────────────────────────────────────────────────────

module load singularity

mkdir -p "${OUTPUT_PATH}"

singularity exec \
  -B "${DATA_PATH}:/data" \
  -B "${OUTPUT_PATH}:/output" \
  "${SIF_PATH}" \
  python /app/facts_dashboard.py \
  --exp-root /data/ \
  --output /output/dashboard.html

echo "Dashboard saved to ${OUTPUT_PATH}/dashboard.html"
