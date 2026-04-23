# FACTS Dashboard — Developer & User Reference Guide

**Document:** facts_dashboard_code_guide  
**File described:** `facts_dashboard.py`  
**Author:** Tarun Theegela (tt633)  
**Date:** April 2026  
**Version:** 1.1.4  

---

# 1. What Is This File?

`facts_dashboard.py` is a single Python script that reads sea-level projection output files produced by **FACTS** (Framework for Assessing Changes To Sea-level) and generates a fully self-contained, interactive HTML dashboard — no web server, no internet connection, no installation required by the end user. Open the HTML file in any modern browser and the full dashboard works.

The dashboard shows sea-level projections from 2005 to 2300 for up to 4 SSP emissions scenarios, 7 ice-sheet/ocean workflows, 7 sea-level components, and up to 24 (or more) tide gauge station locations — all configurable interactively in the browser.

---

# 2. Who Is This For?

This guide is for anyone — scientist, engineer, student, or collaborator from another field — who wants to understand **how the dashboard works internally**: what data it reads, how that data is processed, and how the interactive browser UI is constructed.

No prior knowledge of FACTS is required. Basic familiarity with Python is assumed.

---

# 3. Technology Stack

| Library | Version | Role |
|---|---|---|
| Python | ≥ 3.9 | Language runtime |
| **xarray** | ≥ 2023 | Reads NetCDF4 (.nc) files as labelled arrays |
| **numpy** | ≥ 1.24 | Quantile computation across large sample arrays |
| **pandas** | ≥ 2.0 | Reads location.lst CSV file |
| **Bokeh** | ≥ 3.4 | Builds the interactive browser UI; outputs a single self-contained HTML |
| netCDF4 | ≥ 1.6 | Backend used by xarray to open .nc files |

**Why Bokeh?** Bokeh is the only Python plotting library that can embed a full interactive UI (dropdowns, sliders, checkboxes, callbacks) into a single self-contained HTML file with no server. The entire dashboard — all data, all JavaScript, all CSS — lives in one file that can be emailed, put on a USB drive, or archived.

**Why not matplotlib?** Matplotlib produces static images (PDF, PNG). It has no browser interactivity and cannot produce a self-contained HTML.

**Why not Plotly Dash?** Dash requires a running Python web server. The dashboard must work offline and without any server process — Bokeh's `INLINE` resource mode satisfies this; Dash does not.

---

# 4. Input Data: What FACTS Produces

FACTS runs a Monte Carlo simulation with thousands of samples per scenario. For each SSP scenario and sea-level component, it outputs a `.nc` (NetCDF4) file with the shape:

```
sea_level_change[samples, years, locations]
```

- **samples** — typically 10,000 to 20,000 Monte Carlo draws
- **years** — discrete time steps (e.g. 2020, 2030, ..., 2300)
- **locations** — tide gauge station IDs (e.g. 24 Indian Ocean stations, or 1017 global stations)

The value unit is **millimetres** relative to the experiment base year.

### Input directory structure

```
exp.alt.emis/
├── coupling.ssp126/
│   ├── location.lst          ← tide gauge station list (name, id, lat, lon)
│   └── output/
│       ├── coupling.ssp126.total.workflow.wf1e.local.nc
│       ├── coupling.ssp126.total.workflow.wf1e.global.nc
│       ├── coupling.ssp126.emuAIS.emulandice.AIS_localsl.nc
│       └── ...
├── coupling.ssp245/
│   └── output/ ...
└── coupling.ssp585/
    └── output/ ...
```

Each `coupling.sspXXX/output/` folder can contain up to ~100 `.nc` files covering different combinations of: SSP scenario, component, workflow, and scale (local vs global).

---

# 5. Data Flow Overview

The script runs in four stages:

```
Stage 1 — Discovery
  Scan the experiment folder → find all SSP directories, workflows, locations

Stage 2 — Loading + Quantile Computation
  Open each .nc file → collapse 10,000 samples → compute 5 percentiles (p5, p17, p50, p83, p95)
  Store results in data_dict (a flat Python dict, keyed by a compound string)

Stage 3 — Dashboard Construction
  Build Bokeh widgets (dropdowns, sliders, checkboxes)
  Embed data_dict as JSON inside JavaScript callbacks
  Construct layout (line plot + tables + bar chart)

Stage 4 — Save
  Serialize everything (data + JS + CSS) into a single .html file
```

---

# 6. The `data_dict` — Central Data Structure

All sea-level data in the dashboard lives in one Python dictionary called `data_dict`. Every time series for every combination of SSP, component, workflow, scale, and location is a single entry in this dict.

### Key format

```
"{ssp}|{component}|{wf}|{scale}|{loc_id}"
```

**Example keys:**
```
"ssp585|total|wf1e|local|596"        → total RSL at Karachi (ID 596), wf1e, ssp585
"ssp126|AIS|wf2e|global|-1"          → AIS contribution to global mean SL, wf2e, ssp126
"ssp370|sterodynamics|wf3f|local|12" → sterodynamic contribution at station 12
```

### Key components

| Token | Values | Meaning |
|---|---|---|
| ssp | ssp126, ssp245, ssp370, ssp585 | Emissions scenario |
| component | total, AIS, GrIS, glaciers, sterodynamics, landwaterstorage, vlm | Sea-level component |
| wf | wf1e, wf1f, wf2e, wf2f, wf3e, wf3f, wf4 | Ice-sheet workflow |
| scale | local, global | Local RSL at tide gauge vs global mean SL |
| loc_id | -1 (global mean) or positive integer (tide gauge ID) | Location |

### Value format

Each entry is a dict with six lists, all in millimetres rounded to 1 decimal place:

```python
{
    "years": [2020, 2030, ..., 2300],   # 30 time steps
    "vlo":   [12.3, 24.1, ...],         # 5th percentile
    "lo":    [18.7, 34.2, ...],         # 17th percentile
    "med":   [28.4, 52.6, ...],         # 50th percentile (median)
    "hi":    [41.2, 78.3, ...],         # 83rd percentile
    "vhi":   [55.9, 101.4, ...],        # 95th percentile
}
```

**Why 1 decimal place?** Sea-level projections are in millimetres. Uncertainty bands span hundreds of mm by 2100, so sub-millimetre precision (e.g. `134.67892` vs `134.7`) has no scientific value and significantly inflates file size. Rounding to 1 dp reduces the HTML output from ~168 MB to ~66 MB — a 61% reduction.

---

# 7. Constants and Configuration (lines 110–246)

All project-wide settings live at the top of the file as module-level constants. No magic numbers appear in function bodies.

### `SSP_COLORS` (line 110)

```python
SSP_COLORS = {
    "ssp119": "#00adcf",
    "ssp126": "#173c66",
    "ssp245": "#f79420",
    "ssp370": "#e71d25",
    "ssp585": "#951b1e",
}
```

Praveen's standard SSP color palette. Used consistently across the line plot, bar chart, and legend so every SSP is always the same color regardless of which section you're looking at. `ssp119` is included for future use — FACTS has not yet been run for it.

### `SSP_LABELS` (line 119)

Human-readable display names for SSPs (e.g. `"ssp585"` → `"SSP5-8.5"`). Used in dropdown options and table column headers.

### `WF_LABELS` (line 128)

Full descriptions for each of the 7 workflows (e.g. `"wf1e"` → `"wf1e — emulandice AIS+GrIS, emulandice glaciers (to 2100)"`). Used in dropdown option labels.

### `COMPONENT_STYLES` (line 139)

Maps each component to a line style in the plot:

| Component | Style |
|---|---|
| total | dashed |
| AIS | solid |
| GrIS | dotted |
| glaciers | circle markers |
| sterodynamics | diamond markers |
| landwaterstorage | asterisk markers |
| vlm | triangle markers |

This lets the user distinguish components by shape even when colors overlap.

### `WORKFLOW_COMPONENT_FILES` (line 156)

Maps each workflow to the exact `.nc` filename patterns for AIS, GrIS, and glaciers components. Each workflow uses different ice-sheet models, so file naming differs per workflow. This dict is the authoritative lookup used when scanning the output directory.

### `WORKFLOW_COMPONENT_FALLBACK_SUM` (line 196)

Handles the special case of `wf1f` AIS local scale: the `ar5AIS` model outputs East Antarctic (EAIS) and West Antarctic (WAIS) components separately — there is no combined AIS local file. When the combined file is missing, the script automatically sums EAIS + WAIS. This dict defines which components require that fallback and which sub-files to sum.

### `WORKFLOW_INDEPENDENT_COMPONENTS` (line 208)

Sterodynamics (ocean thermal expansion + dynamics), land water storage, and VLM (vertical land motion) are the same file regardless of ice-sheet workflow. Their filename patterns are stored here separately from `WORKFLOW_COMPONENT_FILES`.

### `COMPONENTS` (line 214)

The ordered list of all 7 sea-level components. Drives the order of rows in the component table and the order of options in component dropdowns.

### `QUANTILES` (line 232)

```python
QUANTILES = [0.05, 0.17, 0.50, 0.83, 0.95]
```

The five percentile levels computed from each .nc sample ensemble. Index 0 = p05, 1 = p17, 2 = p50, 3 = p83, 4 = p95. These match IPCC AR6 reporting conventions (likely range = p17–p83; very likely range = p05–p95).

### `_r1` (line 234)

```python
def _r1(arr):
    return [round(float(v), 1) for v in arr]
```

Module-level helper used everywhere data is stored into `data_dict`. Rounds a numpy array to 1 decimal place and converts to a plain Python list (JSON-serialisable).

### Fixed slider bounds (lines 239–244)

```python
XMIN_FIXED = 2020   XMAX_FIXED = 2300
YMIN_FIXED = -500   YMAX_FIXED = 4000
```

Hard limits for the X and Y range sliders. The Y maximum is 4000 mm (4 metres) — sufficient for the most extreme SSP5-8.5 projections through 2300.

---

# 8. Discovery Functions (lines 251–399)

These functions scan the experiment folder structure and collect metadata before any data is loaded.

### `_count_nc_locations` (line 251)

**Purpose:** Open one `.nc` file and return how many tide gauge locations it contains. Used to choose between two output directories when both exist (e.g. `output/` vs `output copy/`) — the directory with more locations is the more complete run.

**Why needed:** During ssp585 development runs, a partial run (1 location) was in `output/` while the full 24-location Indian Ocean run was in `output copy/`. Without this check, the dashboard would silently use the partial run.

### `collect_ssp_entries` (line 270)

**Purpose:** Scan the experiment root directory (and/or explicitly provided SSP folders) and return a list of `(ssp_tag, output_dir, exp_dir)` tuples — one per SSP scenario found.

**How it works:**
1. Iterates over subdirectories named `coupling.ssp*`
2. Confirms each has an `output/` folder containing `*.total.workflow.*.nc` files
3. Calls `_count_nc_locations` to resolve `output/` vs `output copy/` ambiguity
4. Also accepts explicit `--ssp-dir` paths (for runs stored in non-standard directory layouts)

**Returns:** Sorted list of `(ssp_tag, output_dir, exp_dir)`. This list drives everything downstream.

### `discover_workflows` (line 352)

**Purpose:** Scan the `.nc` filenames to find which workflow IDs (wf1e, wf1f, etc.) are actually present in the data. Returns only workflows that exist — partial runs are supported.

**How it works:** Parses the `.total.workflow.{wf}.nc` filename pattern and extracts the workflow token. Sorts results in the canonical order defined by `WF_LABELS`.

### `load_location_list` (line 378)

**Purpose:** Read `location.lst` — a whitespace-separated text file containing one row per tide gauge station (name, id, lat, lon). Returns a list of dicts.

**Key detail:** Uses `engine="python", on_bad_lines="skip"` in `pd.read_csv`. The default C engine raises a `ParserError` when a station name contains a space (e.g. "Port Louis") because the row appears to have 5 tokens instead of 4. The Python engine handles this gracefully.

---

# 9. Data Loading and Quantile Computation (lines 401–818)

### `compute_quantiles` (line 405)

**Purpose:** Open a single FACTS `.nc` file and compute the 5 percentile levels across the sample axis.

**Input:** Path to a `.nc` file  
**Output:** Dict with keys: `years`, `locations`, `q` (shape: 5 × years × locations), `lat`, `lon`

**How it works:**
```
xr.open_dataset(nc_path)
  → ds["sea_level_change"].values   shape: (samples, years, locations)
  → np.quantile(..., axis=0)        shape: (5, years, locations)
```

The sample axis is axis 0. After `np.quantile`, the samples are gone — only the 5 percentile curves remain per year per location. This is the core data reduction step: 20,000 samples collapse to 5 numbers.

### `compute_quantiles_sum` (line 432)

**Purpose:** Same as `compute_quantiles` but sums the `sea_level_change` arrays from multiple `.nc` files before computing percentiles. Used exclusively for `wf1f` AIS local scale (EAIS + WAIS summed before percentile computation, not after — this is statistically correct because the samples are correlated within a single run).

### `_store_result` (line 465)

**Purpose:** Take the output of `compute_quantiles` and write it into `data_dict` and `location_meta`, one entry per location.

**Key logic:**
- Loops over all location IDs in the result
- Builds the compound key string: `"{key_prefix}|{loc_id}"`
- Rounds all quantile arrays to 1 dp via `_r1()`
- Stores lat/lon metadata for each location (used in hover tooltips and location info divs)
- Handles NaN/Inf coordinates gracefully (sets to `None`)

### `_infer_component_from_stem` (line 506)

**Purpose:** Extract the component name from a FACTS `.nc` filename stem. Used in single-NC-file mode where no directory structure provides context.

**Example:** `"coupling.ssp585.emuGrIS.emulandice.GrIS_globalsl"` → `"GrIS"`

**How it works:** Strips the `_{scale}sl` suffix from the last filename token, then matches against known component names. Handles aliases (e.g. `"GIS"` → `"GrIS"`, `"verticallandmotion"` → `"vlm"`).

### `_infer_wf_from_stem` (line 536)

**Purpose:** Heuristically map a filename stem to a workflow ID. Used in single-NC-file mode.

**How it works:** Checks for model name tokens in the filename (e.g. `"bamber19"` → `wf4`, `"larmip"` → `wf2e`, `"fittedismip"` → `wf1f`). Falls back to `wf1e` when only `emulandice` is present (shared by wf1e, wf2e, wf3e — wf1e is the most common).

### `_find_best_location_lst` (line 558)

**Purpose:** Find the `location.lst` file that best covers the location IDs present in a given `.nc` file. Used in single-NC-file mode.

**Why needed:** A single `.nc` file may belong to an SSP directory that has a partial or incomplete `location.lst`. For example, `coupling.ssp585/` might have only 1 station in its `location.lst` while `coupling.ssp126/` has all 24. This function scans all sibling `coupling.ssp*/` directories and picks the file with the most matching IDs.

### `load_single_nc` (line 608)

**Purpose:** Load a single `.nc` file (instead of a full experiment tree) and return all structures needed by `build_dashboard()`.

**What it does:**
1. Parses the filename to infer SSP, component, workflow, and scale
2. Narrows the global `COMPONENTS` list to only the one component present (so dropdowns show only what's available)
3. Runs `compute_quantiles` on the file
4. Finds the best `location.lst` via `_find_best_location_lst`
5. Builds `data_dict`, `locations`, and `location_meta` in the same format as `precompute_all`

This allows the full dashboard (line plot + bar chart + component table) to render from a single file, with the same code path as the multi-file mode.

### `precompute_all` (line 707)

**Purpose:** The main data loading function for multi-file (experiment-tree) mode. Loads all `.nc` files across all SSPs, workflows, components, and scales. Returns `(data_dict, years_ref, location_meta)`.

**Three loading passes:**

**Pass 1 — Total workflow files**  
Loads `coupling.{ssp}.total.workflow.{wf}.{local|global}.nc` for every combination of SSP × workflow × scale. These are the primary sea-level total projection files.

**Pass 2 — Workflow-specific components (AIS, GrIS, glaciers)**  
Uses `WORKFLOW_COMPONENT_FILES` to look up the correct filename per workflow. If a file is missing, checks `WORKFLOW_COMPONENT_FALLBACK_SUM` for a sum-of-sub-files alternative (wf1f AIS local). Missing files without a fallback are silently skipped — partial runs are supported.

**Pass 3 — Workflow-independent components (sterodynamics, lws, vlm)**  
Loads from `WORKFLOW_INDEPENDENT_COMPONENTS` patterns. Because sterodynamics/LWS/VLM are the same regardless of ice-sheet workflow, the result is stored under every workflow key (fan-out). This keeps the JavaScript key lookup uniform — it always uses the full `{ssp}|{comp}|{wf}|{scale}|{loc_id}` key without special-casing workflow-independent components.

**Why fan-out?** The browser-side JavaScript callback always builds the lookup key using all 5 tokens including workflow. If sterodynamics were stored only once under a special key, the JS would need extra logic to detect workflow-independent components and look them up differently. Storing the same data under every workflow key avoids that entirely. The storage cost is small (5 quantile arrays × n_locations, duplicated 7 times).

---

# 10. HTML Helper Functions (lines 824–907)

Small utility functions that generate HTML strings used in the dashboard layout.

### `_color_box_html` (line 824)
Returns an 18×18 px colored square div. Shown next to each line slot to indicate its SSP color.

### `_style_box_html` (line 843)
Returns a Unicode text preview of the line style (e.g. `— — —` for dashed, `⋅ ⋅ ⋅` for dotted). Shown next to each line slot to indicate which component style is active.

### `_loc_info_html` (line 848)
Returns a small HTML block showing location ID, name, latitude, and longitude. Displayed beside each line slot and updated reactively when the user changes the location dropdown.

### `_workflow_table_html` (line 860)
Returns a full HTML table showing the workflow reference from **Kopp et al. (2023), Table 2** — which GrIS/AIS/glaciers model each workflow uses. Embedded at the bottom of the dashboard as a reference for users unfamiliar with FACTS workflow naming.

---

# 11. Dashboard Section Builders (lines 913–1689)

The dashboard is split into four distinct visual sections, each built by a dedicated function. All four sections share the same `data_dict` but have independent controls.

### `_build_table_section` (line 913)

**What it shows:** A Bokeh `DataTable` where **rows = workflows** and **columns = SSPs**. Each cell shows `median / (p17, p83) / [p05, p95]` for the `total` component at a selected year, scale, and location.

**Controls:** Year selector, scale selector (local/global), location selector.

**Purpose:** Replicates the style of Praveen's reference projection tables — the format used in the FACTS GMD paper. Lets users verify the dashboard numbers against published values.

**JavaScript callback (JS_TABLE):** Rebuilds the entire table data on any control change. Iterates workflows × SSPs, looks up each key in `data_dict`, formats the cell text. Fires `source_table.change.emit()` to trigger a Bokeh reactive re-render.

### `_build_component_table_section` (line 1082)

**What it shows:** A Bokeh `DataTable` where **rows = sea-level components** and **columns = SSPs**. Each cell shows `median / (p17, p83) / [p05, p95]` for a selected workflow, year, scale, and location.

**Controls:** Workflow selector, year selector, scale selector, location selector, unit selector (mm/cm/m — shared with the line plot).

**Purpose:** Shows the component breakdown for a given workflow and scenario — which ice sheet or ocean process is contributing how much to total sea-level change.

**JavaScript callback (JS_COMP):** Same structure as JS_TABLE but rows are components instead of workflows. Applies unit scaling (`uf`) and dynamic decimal places (`dp`) based on the selected unit.

### `_build_stacked_bar_section` (line 1253)

**What it shows:** A grouped bar chart. X-axis = tide gauge locations. Within each group, one bar per selected SSP scenario. Y-axis = sea-level change value at the selected quantile, year, workflow, component, and scale.

**Controls:** Workflow, component, scale, year, quantile, SSP checkboxes, location toggle-dropdown, Y range slider, unit selector (mirrored from line plot via `unit_sel_bar`).

**Key design decisions:**

- **Group centers use integer indices** (0, 1, 2, ..., n_locs-1) rather than floats. This avoids floating-point key mismatch when JavaScript updates x-axis tick labels from a `ColumnDataSource`.
- **`CustomJSTickFormatter` backed by a CDS** for x-axis labels. This is the only Bokeh approach that allows reactive label updates from JavaScript — `major_label_overrides` does not update reactively after JS assignment.
- **`unit_sel_bar` is a display-only mirror.** The bar section has its own unit dropdown (`unit_sel_bar`) that stays visually in sync with the line plot unit dropdown (`unit_sel`). However, all actual callbacks (data scaling, axis label, slider reset) are wired to `unit_sel` only — `unit_sel_bar` just syncs its value to `unit_sel` via a one-way callback. This single-source-of-truth design prevents infinite callback loops.
- **Location toggle-dropdown.** A Bokeh `Toggle` button controls the `visible` property of a `CheckboxGroup`. Clicking the button shows/hides the location checklist. This is implemented entirely with native Bokeh widgets — no HTML `<script>` tags (which do not execute when injected via `Div.text`).

**JavaScript callback (JS_BAR):** Rebuilds the flat bar arrays (x positions, heights, colors) from scratch on every control change. Dynamically recalculates bar width and group spacing based on the number of active SSPs. Updates x-axis ticks and labels via `label_cds` so they match the active location selection.

### `build_dashboard` (line 1694)

**Purpose:** The top-level assembler. Creates the line plot (the primary visualization), per-slot widgets, shared controls, and assembles all four sections into the final Bokeh layout.

**Line plot — 6 configurable slots:**

The line plot supports 6 independent projection lines. Each slot is fully configurable: workflow, SSP, component, scale, and location. Because Bokeh's `CustomJS` cannot create new renderers at runtime, all 7 renderer types (1 band + 7 line/marker styles) are pre-created for every slot at Python time. Only the renderer matching the selected component is made visible; the rest are hidden. When the user changes the component dropdown, the JavaScript callback hides all renderers and shows only the one matching the new selection.

**JavaScript callbacks:**

- **JS_UPDATE** — Fires when any slot selector (workflow, SSP, component, scale, location) changes, or when the shading band or unit selector changes. Looks up the new key in `data_dict`, scales values by the unit factor, updates `source.data`, updates colors and styles, and refreshes the location info div.
- **JS_VISIBILITY** — Fires only when the show/hide checkbox is toggled. Separate from JS_UPDATE to avoid unnecessary data re-reads on a simple visibility toggle.

**Unit selector (`unit_sel`):**

A global `Select` widget (mm / cm / m) added to the line plot controls row. When changed:
1. JS_UPDATE fires for all 6 slots (data scaled)
2. JS_COMP fires for the component table (values scaled)
3. JS_BAR fires for the bar chart (bar heights scaled)
4. A separate callback resets y-slider bounds and axis label for the line plot
5. A separate callback resets y-slider bounds and axis label for the bar chart
6. `unit_sel_bar` syncs its display value

**Why `y_axis=p.yaxis[0]` passed as explicit arg?**  
In Bokeh's CustomJS, writing `p.yaxis[0].axis_label = "..."` inside JS does not update the rendered axis label — `p.yaxis` inside JS is a JavaScript proxy that does not support index access. The correct approach is to pass the axis model as an explicit named arg (`y_axis=p.yaxis[0]`) in the `args` dict, then write `y_axis.axis_label = "..."` inside JS. This triggers a proper model property change.

---

# 12. Single NC File Mode (`--single-nc-file`)

When invoked with `--single-nc-file path/to/file.nc`, the script bypasses the experiment-tree scanner entirely and loads a single `.nc` file. This mode is useful for:
- Users with individual component files (e.g. from a JPL model pipeline)
- Quick inspection of one file without a full experiment directory

**Behavioural differences in single-NC mode:**

| Feature | Normal mode | Single-NC mode |
|---|---|---|
| SSP options | All SSPs found | 1 SSP (from filename) |
| Component options | All 7 | 1 (from filename) |
| Workflow options | All found | 1 (inferred from filename) |
| Slot default cycling | Cycles SSPs across 6 slots | Cycles locations across 6 slots |
| Component table | Shown (7 rows) | Hidden (1×1 adds no value) |
| Metadata banner | Not shown | Shown (SSP, component, wf, year range, n locations) |

---

# 13. CLI Entry Point — `main()` (line 2212)

The `main()` function handles argument parsing and orchestrates the entire pipeline.

**Accepted arguments:**

| Argument | Description |
|---|---|
| `--exp-root DIR` | Root directory containing all `coupling.ssp*` subdirectories |
| `--ssp-dir DIR` | Individual SSP directory (repeat for each SSP) |
| `--single-nc-file FILE` | Single `.nc` file (bypasses experiment tree) |
| `--output FILE` | Output HTML path (default: next to exp-root) |
| `--title TEXT` | Dashboard title string |
| `--verbose` | Enable DEBUG-level logging |

**Three operation modes:**

1. **`--exp-root`** — Scans one root directory for all SSPs automatically. Most common use case.
2. **`--ssp-dir`** (one or more) — Explicitly lists SSP folders from separate runs. Used when SSPs live in different locations.
3. **`--single-nc-file`** — Single-file mode. Bypasses all discovery and goes straight to `load_single_nc`.

**Default output path logic:** If `--output` is not provided, the HTML is written next to the experiment root (or the first SSP dir). This ensures the output is always recoverable — it is never written to a path that disappears when a Docker container exits.

---

# 14. Running the Dashboard

### Local Python (recommended for development)

```bash
conda run -n ve3FACTS python facts_dashboard.py \
    --exp-root /path/to/exp.alt.emis/ \
    --output dashboard.html
open dashboard.html
```

### Docker (no local Python install needed)

```bash
cd facts.plotting.dashboard/
bash docker/build.sh                        # build image once
bash docker/run.sh --exp-root /path/to/exp/ # generate dashboard
```

### Amarel HPC (Singularity, no Docker)

```bash
module load singularity/3.1.0
singularity exec --bind /path/to/data:/mnt/data ~/singularity/facts-viz.sif \
    python facts_dashboard.py \
    --exp-root /mnt/data/exp.alt.emis/ \
    --output /mnt/data/dashboard.html
```

---

# 15. Function Index

| Function | Line | Category | One-line purpose |
|---|---|---|---|
| `_r1` | 234 | Utility | Round float array to 1 dp for data compaction |
| `_count_nc_locations` | 251 | Discovery | Count tide gauge locations in a .nc file |
| `collect_ssp_entries` | 270 | Discovery | Find all SSP output directories |
| `discover_workflows` | 352 | Discovery | Find which workflow IDs are present |
| `load_location_list` | 378 | Discovery | Read tide gauge station list from location.lst |
| `compute_quantiles` | 405 | Loading | Open .nc file and compute p5/p17/p50/p83/p95 |
| `compute_quantiles_sum` | 432 | Loading | Sum multiple .nc files then compute quantiles |
| `_store_result` | 465 | Loading | Write quantile result into data_dict |
| `_infer_component_from_stem` | 506 | Single-NC | Extract component name from filename |
| `_infer_wf_from_stem` | 536 | Single-NC | Infer workflow ID from filename |
| `_find_best_location_lst` | 558 | Single-NC | Find best-matching location.lst for a .nc file |
| `load_single_nc` | 608 | Single-NC | Load one .nc file into dashboard-ready structures |
| `precompute_all` | 707 | Loading | Load all .nc files for multi-file mode |
| `_color_box_html` | 824 | HTML helpers | Colored square div for line slot display |
| `_style_box_html` | 843 | HTML helpers | Unicode line style preview string |
| `_loc_info_html` | 848 | HTML helpers | Location name/lat/lon info div |
| `_workflow_table_html` | 860 | HTML helpers | Kopp et al. 2023 workflow reference table |
| `_build_table_section` | 913 | Dashboard | Workflow × SSP summary table |
| `_build_component_table_section` | 1082 | Dashboard | Component × SSP breakdown table |
| `_build_stacked_bar_section` | 1253 | Dashboard | Grouped bar chart (locations × SSPs) |
| `build_dashboard` | 1694 | Dashboard | Main assembler — line plot + all sections → HTML |
| `main` | 2212 | CLI | Argument parsing and top-level orchestration |
