# Generating Dashboards on Amarel — Step-by-Step Guide
**For:** Reproducing production dashboards from FACTS experiment data on Amarel HPC
**Requires:** Rutgers VPN active, Amarel account, SSH access

---

## Prerequisites

- Rutgers VPN connected (GlobalProtect)
- SSH key configured for `amarel.hpc.rutgers.edu`
- `facts-viz-amd64.sif` container available (see `AMAREL_SETUP.md` to build or locate it)
- FACTS experiment data on scratch: `/scratch/<your-netid>/facts-work/facts/`

---

## Step 1 — Connect to Amarel from your local terminal

```bash
ssh <your-netid>@amarel.hpc.rutgers.edu
```

Verify you can see the experiment data:
```bash
ls /scratch/<your-netid>/facts-work/facts/exp.alt.emis/
```

You should see the experiment folders, e.g.:
```
coupling.ssp585.io/
coupling.ssp585.io.gridded/
coupling.ssp585.io.noemulandice/
```

---

## Step 2 — Upload the latest facts_dashboard.py

Run this from your **local** terminal (not on Amarel):

```bash
scp /path/to/facts_dashboard.py <your-netid>@amarel.hpc.rutgers.edu:/scratch/<your-netid>/facts_dashboard.py
```

> **Note:** The Amarel home directory (`~`) has a tight storage quota. Always upload to `/scratch/<your-netid>/` instead.

Verify the upload on Amarel:
```bash
ls -lh /scratch/<your-netid>/facts_dashboard.py
```

---

## Step 3 — Run the dashboard generator via srun

Use `srun` on your allocated partition. Run one job per experiment folder using `--ssp-dir`.

> **Important:** `sbatch` may fail immediately on some partitions. If that happens, use `srun` instead — it runs interactively and streams output directly to your terminal.

### Small dataset (e.g. 24 locations, ~1 minute)

```bash
srun --partition=<your-partition> --mem=16G --cpus-per-task=4 --time=00:30:00 \
  singularity exec --bind /scratch/<your-netid>:/scratch/<your-netid> \
  /path/to/facts-viz-amd64.sif \
  python /scratch/<your-netid>/facts_dashboard.py \
  --ssp-dir /scratch/<your-netid>/facts-work/facts/exp.alt.emis/coupling.ssp585.io/ \
  --output /scratch/<your-netid>/dashboard_io.html
```

### Large dataset (e.g. 8,460 locations, ~5 minutes)

```bash
srun --partition=<your-partition> --mem=32G --cpus-per-task=4 --time=00:30:00 \
  singularity exec --bind /scratch/<your-netid>:/scratch/<your-netid> \
  /path/to/facts-viz-amd64.sif \
  python /scratch/<your-netid>/facts_dashboard.py \
  --ssp-dir /scratch/<your-netid>/facts-work/facts/exp.alt.emis/coupling.ssp585.io.gridded/ \
  --output /scratch/<your-netid>/dashboard_gridded.html
```

> Use `--mem=32G` for large location counts (1000+). `--mem=16G` is sufficient for smaller runs.

When the job finishes you should see:
```
INFO      Dashboard saved → /scratch/<your-netid>/dashboard_io.html
INFO      Output size      : 2.5 MB
INFO      Done.
```

---

## Step 4 — Download the HTML files to your local machine

Run these from your **local** terminal:

```bash
scp <your-netid>@amarel.hpc.rutgers.edu:/scratch/<your-netid>/dashboard_io.html ./
scp <your-netid>@amarel.hpc.rutgers.edu:/scratch/<your-netid>/dashboard_gridded.html ./
```

> Large files (200+ MB for gridded runs) will take a minute or two to download.

---

## Step 5 — Verify the dashboards

Open each file in Chrome and check:
- No red errors in browser console (Cmd+Option+I on Mac)
- Location dropdown has the expected number of locations
- Line plot shows data for the default slot
- Component table populates correctly

---

## Experiment folder structure

```
/scratch/<your-netid>/facts-work/facts/exp.alt.emis/
├── coupling.ssp585.io/               ← IO run, 24 Indian Ocean tide gauges
│   ├── location.lst
│   └── output/                       ← .nc files
├── coupling.ssp585.io.gridded/        ← Gridded run, 8,460 locations
│   ├── location.lst
│   └── output/                       ← .nc files
└── coupling.ssp585.io.noemulandice/   ← IO run without ice sheet emulator
    ├── location.lst
    └── output/                       ← .nc files
```

---

## Key paths (replace with your own)

| Item | Path |
|------|------|
| Container | `/path/to/singularity/facts-viz-amd64.sif` |
| Script on Amarel | `/scratch/<your-netid>/facts_dashboard.py` |
| Experiment data | `/scratch/<your-netid>/facts-work/facts/exp.alt.emis/` |
| Output | `/scratch/<your-netid>/` |

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `No such file or directory` for script | Home quota exceeded, file not found | Upload script to `/scratch/<your-netid>/` not `~` |
| `sbatch` job fails immediately | Known issue on some partitions | Use `srun` instead |
| `srun: job queued and waiting` | No free nodes on partition | Wait — usually allocates within a minute |
| Dashboard shows no locations | `--ssp-dir` pointing to `output/` subfolder | Point to `coupling.ssp585.io/`, not `coupling.ssp585.io/output/` |
| Download very slow | Large file (gridded ~200 MB) | Normal — wait it out |
