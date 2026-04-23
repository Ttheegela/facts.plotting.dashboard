# facts.plotting.dashboard

Generate an interactive, self-contained HTML dashboard from [FACTS](https://github.com/radical-collaboration/facts) sea-level projection outputs.

No FACTS installation required. The output is a **single `.html` file** — open it in any browser, no web server or internet connection needed.

---

## Requirements

| | |
|--|--|
| **Docker ≥ 20** | [Mac](https://docs.docker.com/desktop/install/mac-install/) · [Windows](https://docs.docker.com/desktop/install/windows-install/) · [Linux](https://docs.docker.com/desktop/install/linux-install/) |
| **Python ≥ 3.9** | Only needed if running without Docker |
| **FACTS `.nc` output files** | From a completed FACTS run |

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/Ttheegela/facts.plotting.dashboard.git
cd facts.plotting.dashboard
```

---

## Step 2 — Build the Docker image

```bash
bash docker/build.sh
```

Only needed once. Rebuild after updating `facts_dashboard.py`.

Expected output:
```
Building facts-viz Docker image...
Done. Image built: facts-viz
```

---

## Step 3 — Generate your dashboard

Pick the option that matches your data:

---

### Option A — All scenarios under one folder *(most common)*

```bash
bash docker/run.sh --exp-root /path/to/experiment/
```

Your data should look like this:
```
experiment/
├── coupling.ssp126/
│   ├── location.lst          ← tide gauge names (optional)
│   └── output/
│       ├── coupling.ssp126.total.workflow.wf1e.local.nc
│       └── ...
├── coupling.ssp245/
├── coupling.ssp370/
└── coupling.ssp585/
```

---

### Option B — Scenarios in separate folders

```bash
bash docker/run.sh \
  --ssp-dir /path/to/coupling.ssp126/ \
  --ssp-dir /path/to/coupling.ssp585/
```

Repeat `--ssp-dir` for each folder. Works with any scenario name — not just SSPs (e.g. `rco.LL.nz`).

---

### Option C — Single NetCDF file

```bash
bash docker/run.sh \
  --single-nc-file /path/to/coupling.ssp585.total.workflow.wf1e.local.nc
```

---

### Option D — AR6-style confidence level files

```bash
bash docker/run.sh \
  --confidence-root /path/to/4_confidence_level_files/ \
  --confidence-level medium_confidence
```

Expected structure:
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

## Step 4 — Open the dashboard

The output path is printed when the command finishes. Open the `.html` file in any browser.

To save to a specific location or set a custom title:

```bash
bash docker/run.sh \
  --exp-root /path/to/experiment/ \
  --output   /path/to/dashboard.html \
  --title    "My FACTS Run"
```

---

## All flags

| Flag | Description |
|------|-------------|
| `--exp-root PATH` | Root folder containing all scenario subdirectories |
| `--ssp-dir PATH` | One scenario folder — repeat for multiple |
| `--single-nc-file FILE` | Single total sea-level `.nc` file |
| `--confidence-root DIR` | Root of AR6-style pre-computed confidence level files |
| `--confidence-level LEVEL` | `medium_confidence` or `low_confidence` (default: `medium_confidence`) |
| `--location-lst FILE` | `location.lst` file for tide gauge names — auto-detected if not provided |
| `--output FILE` | Output HTML path (default: `dashboard.html` next to input data) |
| `--title TEXT` | Dashboard title (auto-generated if omitted) |

---

## Supported data types

| Data | Flag |
|------|------|
| Standard SSP runs (`coupling.ssp126`, `ssp245`, etc.) | `--exp-root` or `--ssp-dir` |
| Non-standard scenarios (`rco.LL.nz`, RFF, etc.) | `--ssp-dir` |
| Single workflow output file | `--single-nc-file` |
| AR6-style post-processed confidence files | `--confidence-root` |

---

## Dashboard features

- **Projection plot** — median line + shading bands (17th/83rd or 5th/95th, selectable)
- **6 independent line slots** — each configurable by scenario, workflow, component, scale, and location
- **Component breakdown table** — per-scenario median and uncertainty ranges at any selected year
- **Grouped bar chart** — scenarios side-by-side per tide gauge; starts blank, locations added via search
- **Location search** — selected locations pin to the top of the list
- **Unit selector** — mm, cm, or m; all three sections update simultaneously
- **Scale toggle** — global mean SL or local RSL
- **Workflow selector** — wf1e, wf1f, wf2e, wf2f, wf3e, wf3f, wf4
- **Year / Y-axis sliders** — zoom into any period or range
- **IPCC AR6 SSP color scheme**

---

## Troubleshooting

**`ERROR: facts-viz image not found`**
→ Run `bash docker/build.sh` first.

**`ERROR: Docker is not installed or not in PATH`**
→ Install Docker Desktop and make sure it is running.

**`ERROR: No scenario directories found`**
→ `--exp-root` should point to the folder *containing* the scenario subfolders, not inside one of them.

**Location names show as IDs**
→ Add `location.lst` to the scenario folder, or pass `--location-lst /path/to/location.lst`.

**Dashboard only shows data up to 2100**
→ Only `wf*e` workflows were found. Run `wf*f` or `wf4` in FACTS for projections to 2300.
