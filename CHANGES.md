# CHANGES

This file documents fixes applied to 11 GitHub issues in the [`tt633/facts.plotting.dashboard`](https://github.com/tt633/facts.plotting.dashboard) repo.

Issues **#8, #9, #14, #18** are deferred — they require Box data from Praveen and will be addressed in a follow-up pass.

---

## Fix 1 — Stage requirements.txt before Docker build (closes #1, #3)

**File(s):** `docker/build.sh`
**Root cause:** Dockerfile does `COPY requirements.txt .` but `build.sh` never copied that file into the build context, causing a silent build failure.
**Change:** Added `cp requirements.txt` into the build context directory before `docker build`; added `rm requirements.txt` cleanup afterward.

---

## Fix 2 — Handle multi-token city names in location list CSV (closes #2, #4, #5)

**File(s):** `facts_dashboard.py` — `load_location_list()` (~line 390)
**Root cause:** The C engine aborts when whitespace-delimited rows have more tokens than `names` (e.g. "Port Louis" splits into 2 tokens).
**Change:** Added `engine="python", on_bad_lines="skip"` to `pd.read_csv`.

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

## Fix 9 — Remove dennis_demo directory (closes #11)

**File(s):** `dennis_demo/` (entire directory)
**Root cause:** Single-file NC viewer demo was stale and not part of the dashboard workflow.
**Change:** Removed via `git rm -r dennis_demo/`.

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
