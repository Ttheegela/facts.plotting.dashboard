# Running the FACTS Dashboard on Amarel via Singularity

**Author:** Tarun Theegela (tt633)
**Date:** April 2026
**Status:** Completed ✓

---

## 1. Overview

This document explains how the FACTS Dashboard was containerised and deployed on
**Amarel** — Rutgers University's HPC cluster — using **Singularity/Apptainer**.

The dashboard (`facts_dashboard.py`) reads FACTS output `.nc` files and generates a
self-contained interactive HTML file. Normally you would run it with Python locally.
On Amarel, we run it inside a container to avoid dependency management on the cluster.

---

## 2. Why Singularity — not Docker?

Amarel (like most HPC clusters) **does not allow Docker**. Docker requires a root-level
daemon, which is a security risk on shared infrastructure. Singularity solves this:

| | Docker | Singularity |
|---|---|---|
| Root required? | Yes (daemon) | No (user-space) |
| Allowed on HPC? | Rarely | Yes |
| Image format | `.tar` / layer cache | `.sif` (single file) |
| Runs Docker images? | Native | Yes — via `docker-archive://` |

Singularity can **directly convert** a Docker `.tar` archive into a `.sif` file, so the
workflow is: build Docker locally → export `.tar` → transfer to Amarel → convert to `.sif`.

---

## 3. Architecture Problem: ARM64 vs x86_64

Local development uses an **Apple Silicon Mac (ARM64)**. Amarel runs **x86_64 (Intel/AMD)**.
A Docker image built normally on the Mac cannot run on Amarel — it's the wrong CPU architecture.

**Solution:** Use Docker's `--platform linux/amd64` build flag to cross-compile the image
before exporting it.

```
Local Mac (ARM64)                         Amarel HPC (x86_64)
──────────────────                        ───────────────────
docker build                              module load singularity/3.1.0
  --platform linux/amd64                  singularity build
  -t facts-viz-amd64                        facts-viz.sif
  docker/                                   docker-archive://facts-viz.tar
        │
        ▼
docker save → facts-viz.tar (122 MB)
        │
        ▼  scp
        └─────────────────────────────────▶ Amarel: ~/singularity/facts-viz.tar
```

---

## 4. Step-by-Step Setup

### Step 1 — Connect to Amarel

1. Connect to **Rutgers GlobalProtect VPN** (required if off-campus)
2. Open **Open OnDemand**: https://ondemand.hpc.rutgers.edu
3. Launch a terminal via Clusters → Amarel Shell Access, or SSH:
   ```bash
   ssh tt633@amarel1.rutgers.edu
   ```

---

### Step 2 — Build the Docker image for x86_64 (on local Mac)

Navigate to the dashboard repo on your local machine and build with the `--platform` flag:

```bash
cd /Users/taruntheegela/Desktop/facts.plotting.dashboard

docker build --platform linux/amd64 -t facts-viz-amd64 docker/
```

> **Why `--platform linux/amd64`?**
> Without this flag, Docker on Apple Silicon defaults to ARM64. The resulting image
> will silently fail on Amarel's x86_64 nodes — Singularity will either refuse to
> convert it or the Python process will segfault at runtime.

This builds from `docker/Dockerfile`, which installs:
- `python:3.11-slim` base
- `bokeh`, `xarray`, `numpy`, `pandas`, `netCDF4` (from `requirements.txt`)
- Copies `facts_dashboard.py` as the container entrypoint

---

### Step 3 — Export the Docker image to a `.tar` file

```bash
docker save facts-viz-amd64 -o singularity/facts-viz.tar
```

This produces `singularity/facts-viz.tar` (~122 MB). It is a flat archive of all Docker
image layers, which Singularity reads via the `docker-archive://` URI scheme.

---

### Step 4 — Transfer to Amarel via SCP

```bash
scp singularity/facts-viz.tar tt633@amarel1.rutgers.edu:~/singularity/
```

For the full FACTS simulation runtime (used for running FACTS itself, not just the dashboard):

```bash
scp singularity/facts_io.tar tt633@amarel1.rutgers.edu:~/singularity/
```

Wait for the transfer to complete. Check the size on Amarel to confirm:

```bash
ssh tt633@amarel1.rutgers.edu "ls -lh ~/singularity/"
```

---

### Step 5 — Build the Singularity `.sif` image on Amarel

> **Do not run this on the login node.** Large builds get killed. Always use an
> interactive compute node via `srun`.

#### 5a. Request a compute node

```bash
srun --partition=main --ntasks=1 --mem=16G --time=01:00:00 --pty bash
```

Wait for the node to be allocated (usually < 1 minute on off-peak hours).

#### 5b. Load the Singularity module

```bash
module load singularity/3.1.0
```

Singularity is **not available by default** on Amarel. You must load the module every
session before any `singularity` command.

#### 5c. Convert `.tar` → `.sif`

```bash
cd ~/singularity/
singularity build facts-viz.sif docker-archive://facts-viz.tar
```

This reads the Docker archive and produces `facts-viz.sif` — a single portable file
that can be run anywhere on Amarel without rebuilding.

For the FACTS runtime image:

```bash
singularity build facts_io.sif docker-archive://facts_io.tar
```

---

## 5. Hello World — Verify the Container Works

Before running the full dashboard, verify the Singularity image is healthy with a
sequence of progressively more complex tests.

### Test 1 — Container is alive

```bash
module load singularity/3.1.0
singularity exec ~/singularity/facts-viz.sif echo "Hello from Singularity"
```

**Expected output:**
```
Hello from Singularity
```

This confirms: image loads, exec works, shell is responsive.

---

### Test 2 — Correct Python version inside the container

```bash
singularity exec ~/singularity/facts-viz.sif python --version
```

**Expected output:**
```
Python 3.11.x
```

---

### Test 3 — Dependencies are installed correctly

```bash
singularity exec ~/singularity/facts-viz.sif python -c "
import bokeh, xarray, numpy, pandas, netCDF4
print('bokeh   :', bokeh.__version__)
print('xarray  :', xarray.__version__)
print('numpy   :', numpy.__version__)
print('pandas  :', pandas.__version__)
print('netCDF4 :', netCDF4.__version__)
print('All dependencies OK')
"
```

**Expected output (versions may vary slightly):**
```
bokeh   : 3.4.x
xarray  : 2024.x.x
numpy   : 1.26.x
pandas  : 2.x.x
netCDF4 : 1.6.x
All dependencies OK
```

If any import fails, the image was built incorrectly — rebuild with Step 2–5.

---

### Test 4 — Dashboard script is present and importable

```bash
singularity exec ~/singularity/facts-viz.sif python -c "
import subprocess, sys
result = subprocess.run(
    ['python', 'facts_dashboard.py', '--help'],
    capture_output=True, text=True
)
print(result.stdout[:500])
"
```

Or more directly:

```bash
singularity exec ~/singularity/facts-viz.sif python facts_dashboard.py --help
```

**Expected output:** The usage/help text for `facts_dashboard.py`, listing
`--exp-root`, `--ssp-dir`, `--output`, `--title` flags.

---

### Test 5 — Full Hello World: generate a dashboard from data on Amarel

Once FACTS output data is on Amarel (e.g. at `~/data/exp.alt.emis/`), generate a
dashboard end-to-end:

```bash
module load singularity/3.1.0

singularity exec \
  --bind ~/data:/data \
  ~/singularity/facts-viz.sif \
  python facts_dashboard.py \
    --exp-root /data/exp.alt.emis/ \
    --output   /data/dashboard.html \
    --title    "FACTS Hello World — Amarel"
```

**What `--bind` does:** It mounts a host directory into the container.
`~/data` on Amarel becomes `/data` inside the container, so the script can
read `.nc` files and write the HTML output back to the host filesystem.

**Expected result:**
```
[facts_dashboard] Collecting SSP entries from /data/exp.alt.emis/ ...
[facts_dashboard] Found N SSP entries: ssp126, ssp245, ssp370, ssp585
[facts_dashboard] Pre-computing all data...
[facts_dashboard] Saving dashboard → /data/dashboard.html
[facts_dashboard] Done.
```

The file `~/data/dashboard.html` then exists on Amarel and can be downloaded via
Open OnDemand's file browser and opened locally in any browser.

---

## 6. Running as a SLURM Batch Job

For longer runs (e.g. large gridded datasets), use a SLURM script instead of an
interactive session:

```bash
#!/bin/bash
#SBATCH --job-name=facts-dashboard
#SBATCH --partition=main
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=facts_dashboard_%j.log

module load singularity/3.1.0

singularity exec \
  --bind ~/data:/data \
  ~/singularity/facts-viz.sif \
  python facts_dashboard.py \
    --exp-root /data/exp.alt.emis/ \
    --output   /data/dashboard.html
```

Submit with:

```bash
sbatch run_dashboard.sh
```

Monitor with:

```bash
squeue -u tt633
```

---

## 7. Images Built and Confirmed Working

| Image | Source `.tar` | Size | Purpose | Status |
|-------|--------------|------|---------|--------|
| `facts-viz.sif` | `facts-viz.tar` | 122 MB | Dashboard HTML generator | ✓ Working |
| `facts_io.sif` | `facts_io.tar` | 584 MB | Full FACTS simulation runtime | ✓ Working |

Both `.sif` files live in `~/singularity/` on Amarel and are portable — they can be
copied to other Amarel users' directories without rebuilding.

---

## 8. Quick Reference

| Task | Command |
|------|---------|
| Load Singularity | `module load singularity/3.1.0` |
| Interactive compute node | `srun --partition=main --ntasks=1 --mem=16G --time=01:00:00 --pty bash` |
| Hello World check | `singularity exec ~/singularity/facts-viz.sif echo "Hello from Singularity"` |
| Check Python version | `singularity exec ~/singularity/facts-viz.sif python --version` |
| Check dependencies | `singularity exec ~/singularity/facts-viz.sif python -c "import bokeh, xarray, numpy, pandas, netCDF4; print('OK')"` |
| Run dashboard | `singularity exec --bind ~/data:/data ~/singularity/facts-viz.sif python facts_dashboard.py --exp-root /data/exp.alt.emis/ --output /data/dashboard.html` |
| Amarel portal | https://ondemand.hpc.rutgers.edu |
| Login nodes | `amarel1.rutgers.edu`, `amarel2.rutgers.edu` |

---

## 9. Key Gotchas

- **Always `module load singularity/3.1.0`** before any `singularity` command — it is not in PATH by default
- **Never run `singularity build` on a login node** — use `srun` to get a compute node first
- **Always use `--bind`** to mount host directories — the container has no access to Amarel's
  filesystem by default
- **Platform flag is mandatory** when building on Apple Silicon (`--platform linux/amd64`)
- The `.sif` file is read-only — it is not a shell environment you live in, just an image
  you `exec` commands into
- Amarel maintenance windows (e.g. April 21–22) can last 2–4 days and occasionally cause
  data loss — always keep local backups of `.tar` files before a maintenance window
