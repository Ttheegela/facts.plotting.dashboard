# FACTS Dashboard — Amarel HPC Setup
**Rutgers Amarel | Singularity | linux/amd64**

---

## Why Singularity?

The FACTS dashboard generator depends on a specific Python environment (Bokeh, xarray, netCDF4, numpy, pandas). Singularity packages this into a single portable `.sif` image that:

- Runs identically on any Amarel node with no module conflicts
- Requires no Python install — one command generates the dashboard
- Is the standard container runtime on Rutgers Amarel (Docker is not available on HPC)

---

## Quick Start — Use the Pre-Built Container

A pre-built and verified container is available at the shared project path:
`/projects/kopp/tt633/singularity/facts-viz-amd64.sif`

No copy needed — run it directly:

```bash
module load singularity

singularity exec \
  -B /path/to/your/data:/data \
  -B /path/to/output:/output \
  /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  python /app/facts_dashboard.py \
  --exp-root /data/ \
  --output /output/dashboard.html
```

Replace `/path/to/your/data` with the absolute path to your FACTS output on Amarel and `/path/to/output` with where you want the HTML saved (e.g. `/scratch/<your-netid>/output`).

---

## Build the Container From Scratch

Only needed if the dashboard script has been updated.

### Step 1 — Build AMD64 image on Mac
```bash
bash docker/build_amd64.sh
```
This creates `amarel/facts-viz-amd64.tar.gz`.

> **Important:** Always use `build_amd64.sh`, not `build.sh`.  
> Mac ARM builds produce ARM64 images that will not run on Amarel (x86_64).

### Step 2 — Upload tarball to Amarel
Upload `amarel/facts-viz-amd64.tar.gz` via OnDemand:
```
https://ondemand.hpc.rutgers.edu → Files → Home Directory → Upload
```

### Step 3 — Build .sif on Amarel
```bash
module load singularity
singularity build /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  docker-archive:///home/<your-netid>/facts-viz-amd64.tar.gz
```

### Step 4 — Verify it works
```bash
singularity exec /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  python /app/facts_dashboard.py --help
```

---

## Run the Dashboard

### Option A — Full experiment root (multiple SSPs)
```bash
module load singularity

singularity exec \
  -B /path/to/exp.alt.emis:/data \
  -B /path/to/output:/output \
  /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  python /app/facts_dashboard.py \
  --exp-root /data/ \
  --output /output/dashboard.html
```

### Option B — Single SSP directory
```bash
module load singularity

singularity exec \
  -B /path/to/coupling.ssp585:/data \
  -B /path/to/output:/output \
  /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  python /app/facts_dashboard.py \
  --ssp-dir /data/ \
  --output /output/dashboard.html
```

### Option C — Confidence files (post-processed quantiles)
```bash
module load singularity

singularity exec \
  -B /path/to/4_confidence_level_files:/data \
  -B /path/to/output:/output \
  /projects/kopp/tt633/singularity/facts-viz-amd64.sif \
  python /app/facts_dashboard.py \
  --confidence-root /data/ \
  --confidence-level medium_confidence \
  --output /output/dashboard.html
```

**Notes:**
- `-B host_path:container_path` mounts your data into the container
- Always use **full absolute paths** — no `~`
- Output HTML is self-contained — open in any browser, no server needed
- For large datasets (1000+ locations), runs take ~10 minutes — consider using SLURM

---

## Run as a SLURM Batch Job

For large datasets (1000+ locations), submit as a batch job rather than running interactively.

A template SLURM script is provided at `amarel/run_dashboard.slurm`. Edit the three variables at the top of the file:

```bash
SIF_PATH="/projects/kopp/tt633/singularity/facts-viz-amd64.sif"
DATA_PATH="/path/to/your/exp.alt.emis"
OUTPUT_PATH="/scratch/<your-netid>/output"
```

Then submit:
```bash
sbatch amarel/run_dashboard.slurm
```

Monitor the job:
```bash
squeue -u <your-netid>
```

---

## Verified Configuration

| Item | Value |
|------|-------|
| Singularity version | 3.1.0 |
| Container base | python:3.11-slim (linux/amd64) |
| Load command | `module load singularity` |
| Tested on | Amarel1 login node + compute nodes |
| Location fix | `sep="\t"` — all 1030 locations load correctly |

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `exec format error` | Wrong architecture (ARM64 image on AMD64 node) | Rebuild using `build_amd64.sh` |
| `No such file or directory` for `.sif` | Tilde `~` not expanding in singularity path | Use full path `/home/<netid>/...` |
| `command not found: singularity` | Module not loaded | Run `module load singularity` first |
| `permission denied` on data path | Data folder not readable | Check folder permissions with `ls -la` |
