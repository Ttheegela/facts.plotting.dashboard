# facts.plotting.dashboard

Generate an interactive, self-contained HTML dashboard from [FACTS](https://github.com/radical-collaboration/facts) sea-level projection outputs — no FACTS installation required.

The output is a **single `.html` file** you can open in any browser. No web server. No internet connection.

---

## What you need

| Requirement | Notes |
|-------------|-------|
| **Docker ≥ 20** | [Mac](https://docs.docker.com/desktop/install/mac-install/) · [Windows](https://docs.docker.com/desktop/install/windows-install/) · [Linux](https://docs.docker.com/desktop/install/linux-install/) |
| **Python ≥ 3.9** | Only needed if running without Docker |
| **FACTS `.nc` output files** | From a completed FACTS run |

---

## Quick start

```bash
# 1. Clone (one time)
git clone https://github.com/Ttheegela/facts.plotting.dashboard.git
cd facts.plotting.dashboard

# 2. Build the Docker image (one time)
bash docker/build.sh

# 3. Generate your dashboard
bash docker/run.sh --exp-root /path/to/your/experiment/
```

The dashboard HTML is saved next to your data folder. Open it in any browser.

---

## Setup in detail

### Step 1 — Clone the repository

```bash
git clone https://github.com/Ttheegela/facts.plotting.dashboard.git
cd facts.plotting.dashboard
```

Only needed once.

---

### Step 2 — Build the Docker image

```bash
bash docker/build.sh
```

Builds a local Docker image called `facts-viz`. Only needed once (rebuild after updating `facts_dashboard.py`).

```
Building facts-viz Docker image...
Done. Image built: facts-viz
```

---

### Step 3 — Generate your dashboard

Choose the option that matches your data layout:

---

#### Option A — All scenarios under one folder *(most common)*

Use when all SSP or scenario folders are under a single parent directory.

```bash
bash docker/run.sh --exp-root /path/to/experiment/
```

Example folder structure:
```
experiment/
├── coupling.ssp126/
│   ├── location.lst
│   └── output/
│       ├── coupling.ssp126.total.workflow.wf1e.local.nc
│       └── ...
├── coupling.ssp245/
├── coupling.ssp370/
└── coupling.ssp585/
```

---

#### Option B — Scenarios in separate folders

Use when each scenario folder is in a different location, or when using non-standard scenario names (e.g. `rco.LL.nz`).

```bash
bash docker/run.sh \
  --ssp-dir /path/to/coupling.ssp126/ \
  --ssp-dir /path/to/coupling.ssp585/
```

---

#### Option C — Single NetCDF file

Use to quickly plot a single total sea-level output file.

```bash
bash docker/run.sh \
  --single-nc-file /path/to/coupling.ssp585.total.workflow.wf1e.local.nc
```

---

#### Option D — AR6-style confidence level files

Use for pre-computed AR6-style quantile files from post-processing.

```bash
bash docker/run.sh \
  --confidence-root /path/to/4_confidence_level_files/ \
  --confidence-level medium_confidence
```

Expected structure inside `--confidence-root`:
```
4_confidence_level_files/
├── medium_confidence/
│   └── ssp585/
│       ├── total_ssp585_medium_confidence_values.nc
│       ├── AIS_ssp585_medium_confidence_values.nc
│       └── ...
└── low_confidence/
    └── ...
```

---

### Optional flags

```bash
bash docker/run.sh \
  --exp-root /path/to/experiment/ \
  --output   /path/to/dashboard.html \
  --title    "My FACTS Run"
```

---

## All command-line flags

| Flag | Description |
|------|-------------|
| `--exp-root PATH` | Root folder containing all scenario subdirectories |
| `--ssp-dir PATH` | Path to one scenario folder — repeat for multiple scenarios |
| `--single-nc-file FILE` | Path to a single total sea-level `.nc` file |
| `--confidence-root DIR` | Root of AR6-style pre-computed confidence level files |
| `--confidence-level LEVEL` | Confidence sub-folder to load (`medium_confidence` or `low_confidence`; default: `medium_confidence`) |
| `--location-lst FILE` | Path to a `location.lst` file for resolving tide gauge names (optional — auto-detected if not provided) |
| `--output FILE` | Where to write the HTML output (default: `dashboard.html` next to the input data) |
| `--title TEXT` | Title displayed in the dashboard header (auto-generated if omitted) |

> Use one of `--exp-root`, `--ssp-dir`, `--single-nc-file`, or `--confidence-root` — not more than one mode at a time.

---

## Supported data types

| Data type | How to load |
|-----------|-------------|
| Standard SSP runs (`coupling.ssp126`, `ssp245`, etc.) | `--exp-root` or `--ssp-dir` |
| Non-standard scenarios (`rco.LL.nz`, RFF, etc.) | `--ssp-dir` |
| Single total workflow file | `--single-nc-file` |
| AR6-style post-processed confidence files | `--confidence-root` + `--confidence-level` |

---

## Expected input structure

```
experiment/
├── coupling.ssp585/
│   ├── location.lst                                       ← tide gauge names (optional)
│   └── output/
│       ├── coupling.ssp585.total.workflow.wf1e.local.nc  ← local RSL total
│       ├── coupling.ssp585.total.workflow.wf1e.global.nc ← global mean SL total
│       ├── coupling.ssp585.emuAIS.emulandice.AIS_localsl.nc
│       ├── coupling.ssp585.GrIS1f.FittedISMIP.GrIS_globalsl.nc
│       └── ...
└── rco.LL.nz/                                             ← non-standard scenario name supported
    └── output/
        └── ...
```

The dashboard auto-discovers all scenarios, workflows (wf1e–wf4), components, and tide gauge locations. Non-standard scenario names are fully supported. Missing files are skipped gracefully — partial runs work fine.

---

## Dashboard features

| Feature | Description |
|---------|-------------|
| **Projection plot** | Median line + shading bands (17th/83rd or 5th/95th percentile, user-selectable) |
| **6 line slots** | Each independently configurable: scenario, workflow, component, scale, location |
| **Component table** | Per-scenario median and uncertainty ranges for each sea-level component at any year |
| **Grouped bar chart** | Scenarios compared side-by-side per tide gauge; starts blank — add locations via search |
| **Location search** | Type to filter tide gauges; selected locations pin to the top of the list |
| **Unit selector** | Switch between mm, cm, and m — all three sections update simultaneously |
| **Scale toggle** | Global mean SL or local relative SL (RSL) |
| **Workflow selector** | Compare wf1e, wf1f, wf2e, wf2f, wf3e, wf3f, wf4 |
| **Quantile selector** | Bar chart shows any percentile: 5th, 17th, median, 83rd, or 95th |
| **Year / Y-axis sliders** | Zoom into any time period or sea-level range |
| **Visibility checkboxes** | Toggle individual lines on or off |
| **SSP color scheme** | IPCC AR6 standard colors (cool-to-warm blue→red) |

---

## Files

| File | Purpose |
|------|---------|
| `facts_dashboard.py` | Main script — the only file needed for direct Python usage |
| `requirements.txt` | Pinned Python dependencies |
| `docker/Dockerfile` | Container definition |
| `docker/build.sh` | Builds the `facts-viz` Docker image |
| `docker/run.sh` | Runs the container with automatic path mounting |

---

## Troubleshooting

**`ERROR: facts-viz image not found`**
→ Run `bash docker/build.sh` first.

**`ERROR: Docker is not installed or not in PATH`**
→ Install Docker Desktop and make sure it is running.

**`ERROR: No scenario directories found`**
→ `--exp-root` should point to the folder *containing* the scenario subfolders, not to one of the subfolders itself.

**Location dropdown shows IDs instead of names**
→ Add `location.lst` to the scenario folder, or pass `--location-lst /path/to/location.lst`.

**Dashboard only shows data up to 2100**
→ Only `wf*e` workflows were found. Run `wf*f` or `wf4` in FACTS for projections to 2300.

**HTML file is very large**
→ Expected for runs with many locations. For 1000+ locations the output is ~56 MB.

---

## Version history

| Version | Changes |
|---------|---------|
| `v1.2.0` *(in progress)* | Scenario generalization (any folder name); HTML ~56 MB for 1030 locations (down from ~664 MB); AR6 confidence file loader; location search with pinned selections; bar chart starts blank; `--location-lst` flag |
| `v1.1.4` | Location toggle-dropdown; shading band selector; bar chart SSP checkboxes; Y-axis range slider |
| `v1.1.3` | Human-readable component labels; corrected SSP colour legend |
| `v1.1.2` | IPCC AR6 SSP color scheme; HTML reduced from 168 MB to 66 MB |
| `v1.1.1` | Grouped bar chart; quantile selector |
| `v1.0.0` | Initial release |
