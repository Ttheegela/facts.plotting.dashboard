# Singularity on Amarel HPC — Setup Report

**Author:** Tarun Theegela (tt633)
**Date:** April 2026
**Status:** Completed ✓

---

## 1. Overview

This report documents the work done to run the FACTS Dashboard and FACTS simulation runtime on **Amarel**, Rutgers University's HPC cluster, via **Open OnDemand** using **Singularity containers**.

The goal was to move computation off local laptops (which have had hardware failures costing $700+) and onto Amarel's infrastructure, which provides ~100 TB storage and scalable compute — enabling runs beyond what a laptop can handle.

---

## 2. Problem Statement

Amarel does **not support Docker** — Docker requires a root daemon which is unavailable on shared HPC clusters. The solution is **Singularity/Apptainer**, which runs containers in user space without root and produces portable `.sif` image files.

Additionally, local development machines (Apple Silicon Mac) run **ARM64** architecture, while Amarel runs **x86_64**. This means Docker images built locally cannot run on Amarel without cross-compilation.

---

## 3. Architecture

```
Local Mac (ARM64)                          Amarel HPC (x86_64)
─────────────────                          ───────────────────
docker build                               module load singularity/3.1.0
  --platform linux/amd64                   singularity build
  -t facts-viz-amd64                         facts-viz.sif
  docker/                                    docker-archive://facts-viz.tar
        │
        ▼
docker save → facts-viz.tar
        │
        ▼ scp
        └──────────────────────────────────▶ Amarel
```

---

## 4. Step-by-Step Setup

### Step 1 — Connect to Amarel

1. Connect to **Rutgers GlobalProtect VPN**
2. Open **Open OnDemand** portal: https://ondemand.hpc.rutgers.edu
3. Launch a terminal (or SSH to `amarel1` / `amarel2`)

---

### Step 2 — Build Docker image for x86_64 (on local Mac)

On your local machine, navigate to the dashboard repo and build with the `--platform` flag:

```bash
cd /Users/taruntheegela/Desktop/facts.plotting.dashboard

# Build for linux/amd64 (Amarel's architecture)
docker build --platform linux/amd64 -t facts-viz-amd64 docker/
```

> **Why `--platform linux/amd64`?** Apple Silicon Macs default to ARM64. Without this flag, the image will fail to run on Amarel's x86_64 nodes.

---

### Step 3 — Export Docker image to .tar

```bash
docker save facts-viz-amd64 -o singularity/facts-viz.tar
```

This creates a flat tar archive (`122 MB`) that Singularity can read directly.

---

### Step 4 — Transfer to Amarel

```bash
scp singularity/facts-viz.tar tt633@amarel1.rutgers.edu:~/singularity/
```

For the full FACTS simulation runtime image (larger):

```bash
scp singularity/facts_io.tar tt633@amarel1.rutgers.edu:~/singularity/
```

---

### Step 5 — Build Singularity image on Amarel

For large builds, always use a compute node (not the login node) to avoid getting killed:

```bash
# Request an interactive compute node
srun --partition=main --ntasks=1 --mem=16G --time=01:00:00 --pty bash

# Load Singularity module
module load singularity/3.1.0

# Build .sif from .tar
singularity build facts-viz.sif docker-archive://facts-viz.tar
```

---

### Step 6 — Run on Amarel

```bash
# Load module first
module load singularity/3.1.0

# Run the dashboard generator
singularity exec facts-viz.sif python facts_dashboard.py \
  --exp-root /path/to/exp/ \
  --output dashboard.html
```

---

## 5. Images Built

| Image | Source | Size | Purpose | Status |
|-------|--------|------|---------|--------|
| `facts-viz.sif` | `singularity/facts-viz.tar` | 122 MB | Dashboard HTML generator | ✓ Confirmed working |
| `facts_io.sif` | `singularity/facts_io.tar` | 584 MB | Full FACTS simulation runtime | ✓ Confirmed working |

---

## 6. Amarel Quick Reference

| Item | Detail |
|------|--------|
| VPN | Rutgers GlobalProtect (required off-campus) |
| Portal | https://ondemand.hpc.rutgers.edu |
| Login nodes | `amarel1`, `amarel2` |
| Singularity module | `module load singularity/3.1.0` |
| Large builds | Use `srun` interactive node (see Step 5) |
| Storage | ~100 TB available on Amarel |

---

## 7. Key Notes

- Always load `module load singularity/3.1.0` before any `singularity` command — it is not available by default
- Do **not** run large `singularity build` commands on login nodes — they will be killed; always use `srun`
- The `.sif` file is portable — once built, it can be shared with others on Amarel without rebuilding
- Amarel has been identified as the environment for running Praveen's large-scale datasets (beyond laptop capacity)

---

## 8. Next Steps

- Run SSP5-8.5 with Emulandice only on Amarel and validate output
- Run the full dashboard generator on Praveen's large dataset when ready
- Share this setup guide with Praveen for team onboarding
