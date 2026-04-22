# FACTS Dashboard — Full Reference Report

**Author:** Tarun Theegela (tt633)
**Date:** April 21, 2026
**Repo:** tt633/facts.plotting.dashboard
**Branch:** dev/issue-fixes (testing repo: Ttheegela/facts.plotting.dashboard.testing)

---

# Part 1 — Code Changes (April 2026 Issue-Fixing Session)

12 fixes implemented across `facts_dashboard.py`, Docker scripts, and repo structure.

---

## Fix 1 — Stage requirements.txt before Docker build (closes #1, #3)

**File:** `docker/build.sh`

**Problem:** Dockerfile does `COPY requirements.txt .` but `build.sh` never copied that file into the build context before running `docker build`, causing a silent build failure.

**Fix:** Added `cp requirements.txt` into the build context directory before `docker build`, and `rm requirements.txt` cleanup afterward.

---

## Fix 2 — Handle multi-token city names in location list CSV (closes #2, #4, #5)

**File:** `facts_dashboard.py` — `load_location_list()` (~line 390)

**Problem:** pandas uses the C engine by default for CSV parsing. When reading a whitespace-separated file with 4 named columns (name, id, lat, lon), a station name containing a space (e.g. "Port Louis") splits into 2 tokens, giving the row 5 values instead of 4. The C engine treats this as a malformed row and raises a ParserError, crashing the dashboard before any data loads.

**Fix:** Added `engine="python", on_bad_lines="skip"` to `pd.read_csv`. The Python engine is more flexible with irregular rows, and `on_bad_lines="skip"` discards any row it cannot parse cleanly instead of aborting.

---

## Fix 3 — Log output file size after save (closes #10)

**File:** `facts_dashboard.py` — after dashboard save

**Problem:** No confirmation that the written file was non-empty or correctly sized.

**Fix:** Added `log.info("Output size : %.1f MB", output_path.stat().st_size / (1024*1024))`.

---

## Fix 4 — Write HTML to a recoverable path in --ssp-dir mode (closes #6)

**File:** `facts_dashboard.py` — default output path logic

**Problem:** `--ssp-dir` mode with no `--output` flag wrote the HTML to `/app/facts_dashboard.html` inside the Docker container, which is lost when the container exits.

**Fix:** Replaced single default with a 3-branch if/elif/else: `--exp-root` writes to exp_root dir; `--ssp-dir` writes to first SSP dir; else writes to current working directory.

---

## Fix 5 — Update SSP color palette to Praveen's standard (closes #13)

**File:** `facts_dashboard.py` — `SSP_COLORS` dict

**Problem:** Old palette used IPCC AR6 colors that diverged from project conventions.

**Fix:** Replaced with Praveen's standard palette:

| SSP | Hex Color |
|---|---|
| ssp119 | #00adcf |
| ssp126 | #173c66 |
| ssp245 | #f79420 |
| ssp370 | #e71d25 |
| ssp585 | #951b1e |

Removed `ssp534` entry. SSP119 included in the map for future use — will run FACTS if data is needed.

---

## Fix 6 — Generate legend dynamically from data (closes #16)

**File:** `facts_dashboard.py` — `legend_html`

**Problem:** Static hard-coded HTML listed all SSPs regardless of which were present in the data.

**Fix:** Replaced with a Python f-string that builds color entries by filtering the `ssps` list through `SSP_COLORS`, so the legend only shows SSPs actually present in the loaded data.

---

## Fix 7 — Repurpose quantile dropdown to shading-band selector (closes #15)

**File:** `facts_dashboard.py` — `q_line_sel` widget and `JS_UPDATE` callback

**Problem:** Dropdown controlled which quantile the solid line showed, causing confusion. The median line should always be fixed at p50.

**Fix:** Dropdown repurposed to select shading band: narrow (17th–83rd percentile) or wide (5th–95th percentile). Solid line now always shows the median (d.med). JavaScript reads d.vlo/d.vhi vs d.lo/d.hi based on the selection.

---

## Fix 8 — Move stacked bar below component table (closes #17)

**File:** `facts_dashboard.py` — `layout_items` assembly

**Problem:** `stacked_bar_section` was placed before `comp_table_section`, rendering the bar chart above the breakdown table.

**Fix:** Moved `stacked_bar_section` to after `comp_table_section` in the layout assembly list.

---

## Fix 9 — Remove dennis_demo; fix --single-nc-file in run.sh (closes #11)

**Files:** `dennis_demo/` (removed), `docker/run.sh`

**Problem (dennis_demo):** Single-file NC viewer demo was stale and not part of the dashboard workflow.

**Problem (run.sh):** Three bugs found when testing --single-nc-file mode:
- `--single-nc-file` was not in the case statement and passed through unhandled
- NC file was mounted as a directory instead of a file
- Default HTML output was written to `/mnt/facts_dashboard.html` inside the container — lost on container exit

**Fix:** Removed `dennis_demo/` via git rm. Fixed run.sh to include `--single-nc-file` in the file-aware mount branch (mounts parent directory, passes full container path to file). Added auto-injection of `--output` pointing to the repo folder (host CWD) when `--single-nc-file` is used without an explicit `--output`.

---

## Fix 10 — Consolidate versions/ and sample-dashboards/ into releases/ (closes #12)

**Files:** `versions/`, `sample-dashboards/` → `releases/`

**Problem:** Two separate directories served the same purpose (archiving released outputs), creating redundant structure.

**Fix:** Both directories merged into a new `releases/` directory via git mv; source directories removed.

---

## Fix 11 — Clean up README quick-start and terminology (closes #7)

**File:** `README.md`

**Problem:** Redundant "Quick start" section contained a broken `open dashboard.html` command; "Scenario A/B" label was inconsistent with usage elsewhere.

**Fix:** Removed redundant "Quick start" section; renamed "Scenario A/B" to "Option A/B" in Step 3; added a description sentence under "Quick reference".

---

## Fix 12 — Unit display switcher mm / cm / m (closes #14)

**File:** `facts_dashboard.py` — JS_UPDATE, JS_BAR, JS_COMP callbacks + new widgets

**Problem:** All values were displayed in millimeters with no option to switch units.

**Fix:** Added a global `unit_sel` dropdown (mm / cm / m) to the line plot controls and a synced `unit_sel_bar` mirror dropdown in the bar chart controls. Both stay in sync. All three sections update simultaneously:
- **Line plot:** data arrays scaled by unit factor, y-axis label updates, y-axis slider range resets
- **Bar chart:** bar heights scaled, y-axis label and chart title update
- **Component table:** all quantile values scaled with appropriate decimal places (1 dp mm, 2 dp cm, 4 dp m)

Axis labels updated via explicit Bokeh model args (not p.yaxis[0] inside JS — that does not update reactively).

Y-axis maximum changed from 6000 mm to 4000 mm.

---

# Part 2 — Pending Issues

## Issue #8 — (deferred, Box data required)

Details pending review of issue text and Box data format. Related to the alt_emis or postprocessed datasets.

## Issue #9 — (deferred, Box data required)

Details pending. Likely related to the postprocessed confidence-level files format (pre-computed quantiles).

## Issue #18 — Plot Box data (4-stage task)

**Stage 1 — alt_emis folder:**
- Tested with `alt_emis26/coupling.ssp585` (1017 locations, 20k samples, ssp585 only)
- Output: **675 MB** — too large to open in browser
- Root cause: 50,512 data series embedded as JSON vs 4,872 for 24-location Indian Ocean data
- **Solution needed:** Output size optimization before this dataset is usable

**Stage 2 — alt_emis26 folder:**
- Same structure as alt_emis, newer Feb 2026 run with 20k samples
- Same size problem applies

**Stage 3 — RFF data (rco.LL.nz):**
- Alternate-emissions scenario, non-standard name (no coupling.ssp* prefix)
- Dashboard currently only scans for `coupling.ssp*` directories — cannot load this yet
- **Solution needed:** Generic scenario name support in the experiment scanner

**Stage 4 — Confidence files (postprocessed/):**
- AR6-style post-processing format: pre-computed quantiles (quantiles, years, locations)
- 107 quantile levels, all 4 SSPs, years 2020–2150, 7 components
- Dashboard currently computes quantiles from raw samples — completely different format
- **Solution needed:** New loader that reads pre-computed quantile files directly

---

# Part 3 — Output Size Optimization

The 675 MB output for 1017 locations is the primary blocker for Box data use.

## Background: How size was reduced from 168 MB → 66 MB (v1.1.2)

The dominant driver was **float precision**. Early versions stored all quantile values at full Python precision (e.g. `134.67892456`). In v1.1.2, all values are rounded to 1 decimal place (mm precision) before being written into `data_dict`. Sub-millimetre precision carries no scientific meaning at the scale of sea-level projections — uncertainty bands span hundreds of mm by 2100.

| Version | Size | Notes |
|---|---|---|
| v1.0.0 | ~159 MB | Initial release |
| v1.1.0 | ~168 MB | Stacked bar chart added |
| v1.1.1 | ~168 MB | Grouped bars + quantile selector |
| v1.1.2 | **66 MB** | 1 dp rounding — 61% reduction |
| v1.1.3–v1.1.4 | 66 MB | UX changes only |

## Options to solve the 675 MB problem (1017 locations)

| Approach | Description | Effort |
|---|---|---|
| Reduce time steps | Store only key years (2020, 2050, 2100, 2150, 2200, 2300) instead of all 30 | Low |
| Location subsetting | Embed only a default subset (e.g. 50 locations); add search to load more | Medium |
| Regional dashboards | Split 1017 locations into regional HTML files | Medium |
| Pre-computed format | Use postprocessed quantile files — skip raw sample loading entirely | High |

---

# Part 4 — Amarel HPC / Singularity

## Overview

**Amarel** = Rutgers University HPC cluster. Does not support Docker (root daemon not allowed on shared HPC). Uses **Singularity/Apptainer** instead — runs containers in user space, produces portable `.sif` files.

## Architecture Problem: ARM64 vs x86_64

Local Mac = Apple Silicon (ARM64). Amarel = x86_64. Images must be cross-compiled:

```
Local Mac (ARM64)                          Amarel HPC (x86_64)
─────────────────                          ───────────────────
docker build                               module load singularity/3.1.0
  --platform linux/amd64                   singularity build
  -t facts-viz-amd64                         facts-viz.sif
  docker/                                    docker-archive://facts-viz.tar
        │
        ▼
docker save → facts-viz.tar (122 MB)
        │
        ▼  scp
        └──────────────────────────────────▶ ~/singularity/facts-viz.tar
```

## Images Built (confirmed working on Amarel)

| Image | Source | Size | Purpose |
|---|---|---|---|
| facts-viz.sif | singularity/facts-viz.tar | 122 MB | Dashboard HTML generator |
| facts_io.sif | singularity/facts_io.tar | 584 MB | Full FACTS simulation runtime |

## Step-by-Step Setup

### Step 1 — Connect to Amarel

Connect via Rutgers GlobalProtect VPN (required off-campus), then open OnDemand portal or SSH:

```bash
ssh tt633@amarel1.rutgers.edu
```

### Step 2 — Build Docker image for x86_64 (on local Mac)

```bash
cd /Users/taruntheegela/Desktop/facts.plotting.dashboard
docker build --platform linux/amd64 -t facts-viz-amd64 docker/
```

### Step 3 — Export to .tar

```bash
docker save facts-viz-amd64 -o singularity/facts-viz.tar
```

### Step 4 — Transfer to Amarel

```bash
scp singularity/facts-viz.tar tt633@amarel1.rutgers.edu:~/singularity/
```

### Step 5 — Build .sif on Amarel (use compute node, not login node)

```bash
srun --partition=main --ntasks=1 --mem=16G --time=01:00:00 --pty bash
module load singularity/3.1.0
cd ~/singularity/
singularity build facts-viz.sif docker-archive://facts-viz.tar
```

### Step 6 — Run dashboard on Amarel

```bash
module load singularity/3.1.0
singularity exec --bind /path/to/data:/mnt/data facts-viz.sif \
    python facts_dashboard.py \
    --exp-root /mnt/data/exp.alt.emis/ \
    --output /mnt/data/dashboard.html
```

## Amarel Quick Reference

| Task | Command |
|---|---|
| Load Singularity | module load singularity/3.1.0 |
| Interactive compute node | srun --partition=main --ntasks=1 --mem=16G --time=01:00:00 --pty bash |
| Hello World check | singularity exec ~/singularity/facts-viz.sif echo "Hello from Singularity" |
| Check dependencies | singularity exec ~/singularity/facts-viz.sif python -c "import bokeh, xarray, numpy, pandas, netCDF4; print('OK')" |
| Portal | https://ondemand.hpc.rutgers.edu |
| Login nodes | amarel1.rutgers.edu, amarel2.rutgers.edu |

## Key Gotchas

- Always `module load singularity/3.1.0` before any singularity command — not in PATH by default
- Never run `singularity build` on the login node — use `srun` to get a compute node first
- Always use `--bind` to mount host directories — container has no access to Amarel filesystem by default
- `--platform linux/amd64` is mandatory when building on Apple Silicon
- Amarel maintenance windows can last 2–4 days with risk of data loss — keep local `.tar` backups

---

# Part 5 — Repo Structure

```
facts.plotting.dashboard/
├── facts_dashboard.py       — always the latest version
├── README.md
├── requirements.txt
├── CHANGES.md               — documents all 12 issue fixes
├── docker/
│   ├── Dockerfile
│   ├── build.sh
│   └── run.sh
├── reports/
│   ├── facts_dashboard_report.md/.docx   ← this document
│   └── make_docs.py
├── sample-data/             — gitignored, Box data from Praveen
│   ├── alt_emis/
│   ├── alt_emis26/
│   ├── rco.LL.nz/
│   └── postprocessed/
└── releases/                — merged from versions/ + sample-dashboards/
```
