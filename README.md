# facts.plotting.dashboard

Generate an interactive, self-contained HTML dashboard from [FACTS](https://github.com/radical-collaboration/facts) sea-level projection outputs.
No FACTS installation required — just Docker (or Python ≥ 3.9).
The output is a **single `.html` file** you can open in any browser — no web server, no internet connection required.

> **Example dashboards:** [v1.0.0](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.0.0) · [v1.1.0](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.0) · [v1.1.1](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.1) · [v1.1.2](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.2) · [v1.1.3](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.3) · [v1.1.4](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.4)

---

## Requirements

- **Docker** ≥ 20 (for Docker usage) — [Mac](https://docs.docker.com/desktop/install/mac-install/) · [Windows](https://docs.docker.com/desktop/install/windows-install/) · [Linux](https://docs.docker.com/desktop/install/linux-install/)
- **Python** ≥ 3.9 (for direct usage)
- FACTS output `.nc` files (netCDF4 format) from a completed FACTS run

---

## Quick start

### Option A — Docker (recommended)

```bash
# 1. Clone once
git clone https://github.com/tt633/facts.plotting.dashboard.git
cd facts.plotting.dashboard

# 2. Build the image once (~1 min)
bash docker/build.sh

# 3. Generate a dashboard
bash docker/run.sh --exp-root /path/to/exp.alt.emis/

# 4. Open
open dashboard.html       # macOS
xdg-open dashboard.html   # Linux
```

### Option B — Direct Python

```bash
pip install bokeh xarray numpy pandas netCDF4

python facts_dashboard.py --exp-root /path/to/exp.alt.emis/
```

---

## Step-by-step guide

### Step 1 — Clone the repository

```bash
git clone https://github.com/tt633/facts.plotting.dashboard.git
cd facts.plotting.dashboard
```

You only need to do this once.

---

### Step 2 — Build the Docker image

```bash
bash docker/build.sh
```

Creates a local Docker image called `facts-viz`. Only needs to be done **once**.

Expected output:
```
Building facts-viz Docker image...
Done. Image built: facts-viz
```

---

### Step 3 — Generate your dashboard

**Scenario A — All SSPs under one folder (most common)**

If your FACTS run looks like this:
```
/my/experiment/
├── coupling.ssp126/
├── coupling.ssp245/
├── coupling.ssp370/
└── coupling.ssp585/
```

Run:
```bash
bash docker/run.sh --exp-root /my/experiment/
```

**Scenario B — Each SSP in a separate folder**

```bash
bash docker/run.sh \
  --ssp-dir /path/to/coupling.ssp126/ \
  --ssp-dir /path/to/coupling.ssp585/
```

**Optional — Custom output path and title**

```bash
bash docker/run.sh \
  --exp-root /my/experiment/ \
  --output   /my/experiment/dashboard.html \
  --title    "Indian Ocean SSPs — My Run"
```

---

### Step 4 — Open the dashboard

When the command finishes, it prints the output path:
```
Dashboard saved: /my/experiment/dashboard.html
```

Double-click the file to open it in your browser.

---

## Command-line arguments

| Argument | Description |
|----------|-------------|
| `--exp-root PATH` | Root folder containing `coupling.ssp*/` subdirectories |
| `--ssp-dir PATH` | Path to a single SSP output folder (repeatable) |
| `--output PATH` | Where to write the HTML (default: `dashboard.html` next to first SSP dir) |
| `--title TEXT` | Title shown in the dashboard header |

Use either `--exp-root` **or** one or more `--ssp-dir` flags — not both.

---

## Expected input structure

```
exp.alt.emis/
├── coupling.ssp126/
│   ├── location.lst            ← tide gauge station list (optional)
│   └── output/
│       ├── coupling.ssp126.total.workflow.wf1e.localsl.nc
│       ├── coupling.ssp126.total.workflow.wf1e.globalsl.nc
│       ├── coupling.ssp126.emuAIS.emulandice.AIS_localsl.nc
│       └── ...
└── coupling.ssp585/
    └── output/
        └── ...
```

The script auto-discovers all SSPs, workflows (wf1e–wf4), and tide gauge locations.
Missing files are skipped gracefully — partial runs are supported.

---

## Dashboard features

- **Projection plot** — median line + 17th/83rd + 5th/95th percentile bands
- **6 line slots** — each independently configurable by workflow, SSP, component, scale, and location
- **Workflow selector** — compare wf1e, wf1f, wf2e, wf2f, wf3e, wf3f, wf4
- **Component breakdown table** — per-SSP median projections for each component (AIS, GrIS, glaciers, sterodynamics, etc.) at any year
- **Scale toggle** — global mean SL or local relative SL (RSL)
- **Location selector** — global or any tide gauge station in `location.lst`
- **SSP curves** — SSP126/245/370/585 shown simultaneously for comparison
- **Year / Y-axis range sliders** — zoom into any period or sea-level range
- **Visibility checkboxes** — toggle individual lines on/off
- **Grouped bar chart** — SSP scenarios compared side by side per tide gauge station (not stacked — SSPs are alternative scenarios, not additive)
- **Quantile selector** — bar chart shows any of: 5th, 17th, median (50th), 83rd, or 95th percentile
- **Location dropdown** — toggle-button reveals a checklist of all tide gauge stations; tick any combination to show only those on the bar chart
- **Line quantile selector** — choose which percentile the solid projection line displays (p5/p17/p50/p83/p95)

---

## Files

| File | Purpose |
|------|---------|
| `facts_dashboard.py` | Main Python script — the only file you need to run directly |
| `docker/Dockerfile` | Container definition |
| `requirements.txt` | Pinned Python dependencies |
| `docker/build.sh` | Builds the `facts-viz` Docker image |
| `docker/run.sh` | Runs the container with automatic path mounting |

---

## Troubleshooting

**`ERROR: facts-viz image not found`**
→ Run `bash docker/build.sh` first.

**`ERROR: Docker is not installed or not in PATH`**
→ Install Docker Desktop and make sure it is running before retrying.

**`ERROR: No coupling.ssp* directories found`**
→ The path given to `--exp-root` should point to the folder *containing* the `coupling.ssp*` subfolders, not inside one of them.

**Location dropdown shows station IDs instead of names**
→ `location.lst` is missing. It should be at `{exp-root}/coupling.{ssp}/location.lst`.

**Dashboard only shows data up to 2100**
→ Only `wf*e` workflows were found. Run `wf*f` or `wf4` in FACTS to get projections out to 2300.

---

## Quick reference

```bash
# One-time setup
git clone https://github.com/tt633/facts.plotting.dashboard.git
cd facts.plotting.dashboard
bash docker/build.sh

# Every time — generate dashboard
bash docker/run.sh --exp-root /path/to/your/experiment/
```

---

## Version

`v1.1.4` — Location toggle-dropdown for bar chart (native Bokeh Toggle + CheckboxGroup, multi-select); line plot y-axis fixed at 0 for cross-run comparability; global line quantile selector (p5/p17/p50/p83/p95); bar chart SSP checkbox selector; bar chart Y-axis range slider; x-axis label reactive fix via CustomJSTickFormatter + ColumnDataSource.

`v1.1.3` — UX polish: human-readable component labels in dropdowns; "Line N" row labels replacing repetitive per-widget "(Line N)" titles; corrected SSP colour legend to match actual hex codes; removed placeholder text from header.

`v1.1.2` — IPCC AR6-standard SSP color scheme (cool-to-warm blue→red gradient); HTML weight reduced from 168 MB to 66 MB by rounding projection values to 1 decimal place (mm precision).

`v1.1.1` — Grouped bar chart replacing stacked bars; quantile selector (5th/17th/50th/83rd/95th) for bar chart.

`v1.0.0` — Initial release supporting workflows wf1e–wf4, SSP126/245/370/585,
global and local RSL, Indian Ocean tide gauge locations.