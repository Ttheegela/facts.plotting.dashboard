# facts.plotting.dashboard

Generate an interactive, self-contained HTML dashboard from [FACTS](https://github.com/radical-collaboration/facts) sea-level projection outputs — no FACTS installation required.

The output is a **single `.html` file** you can open in any browser. No web server. No internet connection.

---

## Requirements

| Requirement | Notes |
|-------------|-------|
| **Docker ≥ 20** | [Mac](https://docs.docker.com/desktop/install/mac-install/) · [Windows](https://docs.docker.com/desktop/install/windows-install/) · [Linux](https://docs.docker.com/desktop/install/linux-install/) |
| **Python ≥ 3.9** | Only needed if running without Docker |
| **FACTS `.nc` output files** | From a completed FACTS run |

---

## Setup

### Step 1 — Clone the repository

```bash
git clone https://github.com/Ttheegela/facts.plotting.dashboard.git
cd facts.plotting.dashboard
```

Only needed once.

### Step 2 — Build the Docker image

```bash
bash docker/build.sh
```

Builds a local Docker image called `facts-viz`. Only needed once (rebuild after updating `facts_dashboard.py`).

Expected output:
```
Building facts-viz Docker image...
Done. Image built: facts-viz
```

### Step 3 — Generate your dashboard

Choose the option that matches your data:

**Option A — All scenarios under one folder** *(most common)*

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

**Option B — Scenarios in separate folders**

```bash
bash docker/run.sh \
  --ssp-dir /path/to/coupling.ssp126/ \
  --ssp-dir /path/to/coupling.ssp585/
```

Repeat `--ssp-dir` for each scenario folder. Works with non-standard scenario names (e.g. `rco.LL.nz`).

**Option C — Single NetCDF file**

```bash
bash docker/run.sh \
  --single-nc-file /path/to/coupling.ssp585.total.workflow.wf1e.local.nc
```

**Option D — AR6-style confidence level files**

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

### Step 4 — Open the dashboard

When the command finishes it prints the output path. Double-click the `.html` file to open it in any browser.

To save to a custom location or set a title:

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
| `--output FILE` | Where to write the HTML (default: `dashboard.html` next to the input data) |
| `--title TEXT` | Title shown in the dashboard header (auto-generated if omitted) |

Use one of `--exp-root`, `--ssp-dir`, `--single-nc-file`, or `--confidence-root` — not more than one mode at a time.

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
│       ├── coupling.ssp585.total.workflow.wf1e.local.nc
│       ├── coupling.ssp585.total.workflow.wf1e.global.nc
│       ├── coupling.ssp585.emuAIS.emulandice.AIS_localsl.nc
│       └── ...
└── rco.LL.nz/                                             ← non-standard scenario names supported
    └── output/
        └── ...
```

The dashboard auto-discovers all scenarios, workflows (wf1e–wf4), components, and tide gauge locations. Missing files are skipped gracefully.

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
| **SSP color scheme** | IPCC AR6 standard colors |

---

## Files

| File | Purpose |
|------|---------|
| `facts_dashboard.py` | Main script — only file needed for direct Python usage |
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

---

## Version history

| Version | Key change |
|---------|------------|
| `v1.2.0` *(in progress)* | HTML ~56 MB for 1030 locations (down from ~664 MB); scenario generalization; AR6 confidence file loader; location search with pinned selections |
| `v1.1.4` | Location toggle-dropdown; shading band selector; bar chart SSP checkboxes; Y-axis slider |
| `v1.1.3` | Human-readable component labels; corrected SSP colour legend |
| `v1.1.2` | IPCC AR6 SSP color scheme; HTML 168 MB → 66 MB |
| `v1.1.1` | Grouped bar chart; quantile selector |
| `v1.0.0` | Initial release |
