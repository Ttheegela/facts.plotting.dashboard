# CHANGES

---

## v1.2.0 — HTML size reduction, scenario generalization, and Box data support

### Why v1.2.0?

The most significant change in this release is a **91% reduction in HTML output size** for large datasets.
Before v1.2.0, a 1030-location run produced a ~664 MB HTML file — too large to open in most browsers.
The same run now produces a ~56 MB file, making the dashboard practical for real-world Box datasets.

This was achieved by serializing the full data dictionary **once** as a global JavaScript variable
(`window.FACTS_DATA`) injected into the HTML, instead of duplicating it across every Bokeh CustomJS
callback (previously 7 copies). All callbacks now read from `window.FACTS_DATA` directly.

Combined with support for non-standard scenario names, new data modes, and UI improvements for
navigating large location sets, this release marks a meaningful step change from the v1.1.x series.

---

### Change 12 — HTML output size: ~664 MB → ~56 MB for 1030-location runs (closes #10, #18)

**Root cause:** The `data_dict` object (all projection data) was passed as a `CustomJS` argument to
every callback — Bokeh serialized it once per callback, resulting in 7 duplicate copies embedded in
the HTML for a 1030-location run (~95 MB × 7 ≈ 664 MB).

**Fix:** Removed `data_dict` from all `CustomJS args=` dicts. Instead, after `save()`, the HTML is
post-processed to inject `<script>window.FACTS_DATA = {...};</script>` once before `</head>`.
All four JS callbacks (`JS_UPDATE`, `JS_BAR`, `JS_COMP`, summary table) now read from
`window.FACTS_DATA[key]` directly.

**Note:** Injection uses `</head>` not `<body>` — Bokeh's INLINE bundle contains the literal string
`<body>` as part of its minified JS, so injecting before `<body>` would break the bundle.

**Result:** 664 MB → 56 MB (91% reduction) for 1030 locations × 1 SSP.

---

### Change 13 — Scenario generalization: any folder name supported (closes #8, #9)

**Root cause:** All file path templates were hardcoded with `coupling.{ssp}` prefix. Folders named
`rco.LL.nz`, `rff.LL`, or any non-SSP name were silently skipped.

**Fix:**
- Added `_scenario_tag_from_folder()` — maps folder name to scenario tag (`coupling.ssp126` → `ssp126`, `rco.LL.nz` → `rco.LL.nz`)
- Added `_scenario_file_prefix()` — maps tag back to file prefix for NC filename construction
- Removed `startswith("coupling.ssp")` guards from folder discovery and location list search
- All file templates updated to use `{prefix}` instead of `coupling.{ssp}`

**Result:** Dashboard works with any scenario naming convention without code changes.

---

### Change 14 — AR6-style confidence file loader (closes #18 partial)

**New flags:** `--confidence-root DIR`, `--confidence-level LEVEL`, `--location-lst FILE`

Loads pre-computed AR6-style quantile NC files with shape `(quantiles=107, years, locations)`.
Quantile indices used: p05=7, p17=20, p50=53, p83=86, p95=99.
Component name mapping: `GIS` → `GrIS`, `verticallandmotion` → `vlm`.
Workflow tag: `"conf"`. Location names resolved from `location.lst` if found or explicitly provided.

---

### Change 15 — Location search with pinned selections for bar chart

Selected locations are pinned to the top of the list (checked). Unselected locations appear below,
filtered by the search query. Typing auto-adds matching locations to the pinned set. Clearing the
search restores pinned selections while showing the full unselected list below. Bar chart starts
blank — no locations are pre-selected on load.

---

This file also documents the earlier v1.1.x fixes below.

This file documents fixes applied to GitHub issues in the [`Ttheegela/facts.plotting.dashboard`](https://github.com/Ttheegela/facts.plotting.dashboard) repo.

---

## Fix 1 — Stage requirements.txt before Docker build (closes #1, #3)

**File(s):** `docker/build.sh`
**Root cause:** Dockerfile does `COPY requirements.txt .` but `build.sh` never copied that file into the build context, causing a silent build failure.
**Change:** Added `cp requirements.txt` into the build context directory before `docker build`; added `rm requirements.txt` cleanup afterward.

---

## Fix 2 — Handle multi-token city names in location list CSV (closes #2, #4, #5)

**File(s):** `facts_dashboard.py` — `load_location_list()` (~line 390)
**Root cause:** pandas uses the C engine by default for CSV parsing — it is fast but strict. When reading a whitespace-separated file with 4 named columns (`name`, `id`, `lat`, `lon`), a station name containing a space (e.g. "Port Louis") splits into 2 tokens, giving the row 5 values instead of 4. The C engine treats this as a malformed row and raises a `ParserError`, crashing the dashboard before any data loads.
**Change:** Added `engine="python", on_bad_lines="skip"` to `pd.read_csv`. The Python engine is more flexible with irregular rows, and `on_bad_lines="skip"` discards any row it cannot parse cleanly instead of aborting.

---

## Fix 3 — Log output file size after save (closes #10)

**File(s):** `facts_dashboard.py` — after `log.info("Dashboard saved →...")`
**Root cause:** No confirmation that the written file was non-empty or correctly sized.
**Change:** Added `log.info("Output size : %.1f MB", output_path.stat().st_size / (1024*1024))`.

---

## Fix 4 — Write HTML to a recoverable path in --ssp-dir mode (closes #6)

**File(s):** `facts_dashboard.py` — default output path logic
**Root cause:** `--ssp-dir` mode with no `--exp-root` wrote the HTML to `/app/facts_dashboard.html` inside the Docker container, lost on container exit.
**Change:** Replaced single default with a 3-branch if/elif/else: `--exp-root` → exp_root dir; `--ssp-dir` → first SSP dir; else → cwd.

---

## Fix 5 — Update SSP color palette to Praveen's standard (closes #13)

**File(s):** `facts_dashboard.py` — `SSP_COLORS` dict
**Root cause:** Old palette used IPCC AR6 colors that diverged from project conventions.
**Change:** Replaced with Praveen's standard: `ssp119:#00adcf`, `ssp126:#173c66`, `ssp245:#f79420`, `ssp370:#e71d25`, `ssp585:#951b1e`. Removed `ssp534` entry.

---

## Fix 6 — Generate legend dynamically from data (closes #16)

**File(s):** `facts_dashboard.py` — `legend_html`
**Root cause:** Static hard-coded HTML listed all SSPs regardless of which were present in the data.
**Change:** Replaced with a Python f-string that builds color entries by filtering the `ssps` list through `SSP_COLORS`, so the legend only shows SSPs present in the data.

---

## Fix 7 — Repurpose quantile dropdown to shading-band selector (closes #15)

**File(s):** `facts_dashboard.py` — `q_line_sel` widget + `JS_UPDATE` callback
**Root cause:** Dropdown controlled which quantile the solid line showed, causing confusion; the line should always show the median.
**Change:** Dropdown repurposed to select shading band (narrow = 17–83, wide = 5–95). Solid line now always shows `d.med`; JS reads `d.vlo`/`d.vhi` vs `d.lo`/`d.hi` based on selection.

---

## Fix 8 — Move stacked bar below component table (closes #17)

**File(s):** `facts_dashboard.py` — `layout_items` assembly
**Root cause:** `stacked_bar_section` was placed before `comp_table_section`, rendering the bar chart above the breakdown table.
**Change:** Moved `stacked_bar_section` to after `comp_table_section` in the layout assembly list.

---

## Fix 9 — Remove dennis_demo directory; fix --single-nc-file in run.sh (closes #11)

**File(s):** `dennis_demo/` (entire directory), `docker/run.sh`
**Root cause (dennis_demo):** Single-file NC viewer demo was stale and not part of the dashboard workflow. Praveen requested it be removed and the single-NC plotting capability kept inside `facts_dashboard.py` using the existing `--single-nc-file` flag.
**Root cause (run.sh):** `run.sh` only knew how to mount `--exp-root`, `--ssp-dir`, and `--output` paths into the Docker container. `--single-nc-file` was passed through unhandled, so the container never saw the file. Additionally, the path resolution treated the NC file as a directory mount instead of a file mount, causing the output HTML to be written to `/mnt/facts_dashboard.html` — outside any mounted volume and lost when the container exited.
**Change:** Removed `dennis_demo/` via `git rm`. Fixed `run.sh` to include `--single-nc-file` in the file-aware mount branch (mounts parent directory, passes full container path to the file). Added auto-injection of `--output` pointing to the repo folder (host CWD) when `--single-nc-file` is used without an explicit `--output`, so the HTML always lands in `facts.plotting.dashboard/` instead of inside the data directories.

---

## Fix 10 — Consolidate versions/ and sample-dashboards/ into releases/ (closes #12)

**File(s):** `versions/`, `sample-dashboards/` → `releases/`
**Root cause:** Two separate directories served the same purpose (archiving released outputs), creating redundant structure.
**Change:** Both directories merged into a new `releases/` directory via `git mv`; source dirs removed.

---

## Fix 11 — Clean up README quick-start and terminology (closes #7)

**File(s):** `README.md`
**Root cause:** Redundant "Quick start" section contained a broken `open dashboard.html` command; "Scenario A/B" label was inconsistent with usage elsewhere.
**Change:** Removed redundant "Quick start" section; renamed "Scenario A/B" → "Option A/B" in Step 3; added a description sentence under "Quick reference".
