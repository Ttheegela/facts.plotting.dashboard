#!/usr/bin/env python3
"""
facts_dashboard.py — FACTS Sea-Level Projection Dashboard Generator
Version: 1.0.0

Generates a fully self-contained, interactive HTML dashboard from FACTS output
.nc files. No server required — open the HTML in any browser.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Python ≥ 3.9
  bokeh == 3.8.1   xarray == 2025.12.0   numpy == 1.26.4
  pandas == 2.3.3  netCDF4 == 1.7.4

  Install:  pip install -r requirements.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Single experiment root (all SSPs under one folder):
       python facts_dashboard.py --exp-root exp.alt.emis/

2. Individual SSP folders from separate runs:
       python facts_dashboard.py \\
           --ssp-dir /run1/coupling.ssp126/ \\
           --ssp-dir /run2/coupling.ssp585/

3. Custom output path and title:
       python facts_dashboard.py \\
           --exp-root exp.alt.emis/ \\
           --output   ~/reports/dashboard.html \\
           --title    "Indian Ocean SSP runs"

4. Via Docker (no local Python install needed):
       bash build.sh                          # build image once
       bash run.sh --exp-root /path/to/exp/   # generate dashboard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPECTED INPUT STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  exp.alt.emis/
  ├── coupling.ssp126/
  │   ├── location.lst          (tide gauge station list)
  │   └── output/
  │       ├── coupling.ssp126.total.workflow.wf1e.localsl.nc
  │       ├── coupling.ssp126.total.workflow.wf1e.globalsl.nc
  │       ├── coupling.ssp126.emuAIS.emulandice.AIS_localsl.nc
  │       └── ...
  └── coupling.ssp585/
      └── output/
          └── ...

  The script auto-discovers all SSPs, workflows, and locations present.
  Missing files are skipped gracefully — partial runs are supported.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DASHBOARD FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • 6 independent configurable line slots
    (workflow × SSP × component × scale × location)
  • Components: total, AIS, GrIS, glaciers, sterodynamics,
    landwaterstorage, VLM
  • Scales: Local RSL (at tide gauge) | Global Mean SL
  • Shading: p17–p83 band; lines: p50 median
  • X/Y range sliders (2005–2300)
  • Interactive component×SSP table (select workflow, year,
    scale, and location; matches professor's reference table)
  • Workflows: wf1e, wf1f, wf2e, wf2f, wf3e, wf3f, wf4
    (Kopp et al. 2023, Table 2 / AR6)
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr            # reads NetCDF4 files as labelled arrays

# Bokeh: browser-side interactive plots baked into a single HTML file (no server needed)
from bokeh.io import save
from bokeh.layouts import column, row
from bokeh.models import (
    Checkbox, CheckboxGroup, ColumnDataSource, CustomJS, DataTable, Div,
    CustomJSTickFormatter, FixedTicker, HTMLTemplateFormatter,
    HoverTool, InlineStyleSheet, Legend, LegendItem, Range1d, RangeSlider,
    Select, TableColumn, TextInput, Toggle,
)
from bokeh.plotting import figure
from bokeh.resources import INLINE   # embeds all JS/CSS inline so the HTML is self-contained

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("facts_dashboard")

# ─────────────────────────────────────────────────────────
# Colour + label maps
# ─────────────────────────────────────────────────────────

SSP_COLORS = {
    "ssp119": "#00adcf",   # rgb(0, 173, 207)
    "ssp126": "#173c66",   # rgb(23, 60, 102)
    "ssp245": "#f79420",   # rgb(247, 148, 32)
    "ssp370": "#e71d25",   # rgb(231, 29, 37)
    "ssp585": "#951b1e",   # rgb(149, 27, 30)
}
_FALLBACK_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"]

SSP_LABELS = {
    "ssp119": "SSP1-1.9",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0",
    "ssp585": "SSP5-8.5",
    "ssp534": "SSP5-3.4 overshoot",
}

WF_LABELS = {
    "wf1e": "wf1e — emulandice AIS+GrIS, emulandice glaciers (to 2100)",
    "wf1f": "wf1f — FittedISMIP GrIS, AR5 AIS+glaciers (to 2300)",
    "wf2e": "wf2e — emulandice GrIS, LARMIP AIS, emulandice glaciers (to 2100)",
    "wf2f": "wf2f — FittedISMIP GrIS, LARMIP AIS, AR5 glaciers (to 2300)",
    "wf3e": "wf3e — emulandice GrIS, DeConto21 AIS, emulandice glaciers (to 2100)",
    "wf3f": "wf3f — FittedISMIP GrIS, DeConto21 AIS, AR5 glaciers (to 2300)",
    "wf4":  "wf4  — Bamber19 ice sheets, AR5 glaciers (to 2300)",
    "conf":     "conf — AR6-style pre-computed confidence levels",
    "med_conf": "med_conf — medium-confidence AR6 projections",
    "low_conf": "low_conf — low-confidence AR6 projections",
}

# Component → line style (drives the actual rendered line style)
COMPONENT_STYLES = {
    "total":             "dashed",
    "AIS":               "solid",
    "GrIS":              "dotted",
    "glaciers":          "circle",
    "sterodynamics":     "diamond",
    "landwaterstorage":  "asterisk",
    "vlm":               "triangle",
}

# Workflow-specific component file patterns (AIS, GrIS, glaciers differ by workflow).
# Scale token is either "global" or "local" (inserted before "sl.nc").
# VLM only exists as a local-scale file (no global variant — missing files are skipped).
#
# Key design rule: wf2e and wf2f use the LARMIP model for AIS, which is stochastic —
# each FACTS run uses a different random seed, so wf2e/wf2f totals will differ slightly
# from any reference table produced by a separate run. This is expected, not a bug.
WORKFLOW_COMPONENT_FILES = {
    "wf1e": {
        "AIS":      "emuAIS.emulandice.AIS_{scale}sl.nc",
        "GrIS":     "emuGrIS.emulandice.GrIS_{scale}sl.nc",
        "glaciers": "emuglaciers.emulandice.glaciers_{scale}sl.nc",
    },
    "wf1f": {
        "AIS":      "ar5AIS.ipccar5.icesheets_AIS_{scale}sl.nc",
        "GrIS":     "GrIS1f.FittedISMIP.GrIS_GIS_{scale}sl.nc",
        "glaciers": "ar5glaciers.ipccar5.glaciers_{scale}sl.nc",
    },
    "wf2e": {
        "AIS":      "larmip.larmip.AIS_{scale}sl.nc",
        "GrIS":     "emuGrIS.emulandice.GrIS_{scale}sl.nc",
        "glaciers": "emuglaciers.emulandice.glaciers_{scale}sl.nc",
    },
    "wf2f": {
        "AIS":      "larmip.larmip.AIS_{scale}sl.nc",
        "GrIS":     "GrIS1f.FittedISMIP.GrIS_GIS_{scale}sl.nc",
        "glaciers": "ar5glaciers.ipccar5.glaciers_{scale}sl.nc",
    },
    "wf3e": {
        "AIS":      "deconto21.deconto21.AIS_AIS_{scale}sl.nc",
        "GrIS":     "emuGrIS.emulandice.GrIS_{scale}sl.nc",
        "glaciers": "emuglaciers.emulandice.glaciers_{scale}sl.nc",
    },
    "wf3f": {
        "AIS":      "deconto21.deconto21.AIS_AIS_{scale}sl.nc",
        "GrIS":     "GrIS1f.FittedISMIP.GrIS_GIS_{scale}sl.nc",
        "glaciers": "ar5glaciers.ipccar5.glaciers_{scale}sl.nc",
    },
    "wf4": {
        "AIS":      "bamber19.bamber19.icesheets_AIS_{scale}sl.nc",
        "GrIS":     "bamber19.bamber19.icesheets_GIS_{scale}sl.nc",
        "glaciers": "ar5glaciers.ipccar5.glaciers_{scale}sl.nc",
    },
}

# When a workflow component file is missing, sum these sub-files instead.
# wf1f AIS local: ar5AIS outputs EAIS + WAIS separately — no combined local file exists.
WORKFLOW_COMPONENT_FALLBACK_SUM = {
    "wf1f": {
        "AIS": {
            "local": [
                "ar5AIS.ipccar5.icesheets_EAIS_{scale}sl.nc",
                "ar5AIS.ipccar5.icesheets_WAIS_{scale}sl.nc",
            ]
        }
    }
}

# Workflow-independent components (same file for all workflows).
WORKFLOW_INDEPENDENT_COMPONENTS = {
    "sterodynamics":    "ocean.tlm.sterodynamics_{scale}sl.nc",
    "landwaterstorage": "lws.ssp.landwaterstorage_{scale}sl.nc",
    "vlm":              "k14vlm.kopp14.verticallandmotion_{scale}sl.nc",
}

COMPONENTS = (
    ["total"]
    + list(WORKFLOW_COMPONENT_FILES["wf1e"].keys())
    + list(WORKFLOW_INDEPENDENT_COMPONENTS.keys())
)

COMPONENT_LABELS = {
    "total":            "Total",
    "AIS":              "AIS (Antarctic Ice Sheet)",
    "GrIS":             "GrIS (Greenland Ice Sheet)",
    "glaciers":         "Glaciers",
    "sterodynamics":    "Sterodynamics",
    "landwaterstorage": "Land water storage",
    "vlm":              "VLM (Vertical Land Motion)",
}

# Quantiles to extract from each .nc ensemble.
# Index map used throughout: 0=p05, 1=p17, 2=p50(median), 3=p83, 4=p95
QUANTILES = [0.05, 0.17, 0.50, 0.83, 0.95]

# Confidence files store 107 pre-computed quantiles (no samples axis).
# These indices correspond to p05/p17/p50/p83/p95 in that 107-value array.
_CONF_Q_IDX = {"vlo": 7, "lo": 20, "med": 53, "hi": 86, "vhi": 99}

# Component name normalisation for confidence file filenames.
# Confidence files use "GIS" and "verticallandmotion"; dashboard uses "GrIS" and "vlm".
_CONF_COMP_MAP = {"GIS": "GrIS", "verticallandmotion": "vlm"}

def _r1(arr):
    """Round a float array to 1 decimal place (mm precision). Used throughout for data compaction."""
    return [round(float(v), 1) for v in arr]

# Fixed slider bounds
XMIN_FIXED = 2020
XMAX_FIXED = 2300
YMIN_FIXED = -500
YMAX_FIXED = 4000

# ─────────────────────────────────────────────────────────
# Scenario helpers
# ─────────────────────────────────────────────────────────

def _parse_run_prefix_and_tag(nc_path: Path) -> tuple:
    """
    Read the run prefix and scenario tag directly from an NC filename.
    Splits on '.total.workflow.' — everything before is the run prefix.

    coupling.ssp126.total.workflow.wf1e.local.nc  → ("coupling.ssp126", "ssp126")
    rco.LL.nz.total.workflow.wf1e.local.nc        → ("rco.LL.nz",       "rco.LL.nz")
    src.H.ssp370.total.workflow.wf1e.local.nc     → ("src.H.ssp370",    "H.ssp370")

    The tag is parts[1:] joined — strips the leading segment (coupling / src / etc.)
    only when more than one dot-segment is present. For single-segment prefixes like
    'rco.LL.nz' the whole prefix is used as the tag.
    """
    marker = ".total.workflow."
    stem = nc_path.stem
    if marker not in stem:
        raise ValueError(f"Cannot parse run prefix from {nc_path.name}")
    run_prefix = stem.split(marker, 1)[0]
    parts = run_prefix.split(".")
    # Drop the leading coupling/src/rff wrapper only for well-known wrappers
    known_wrappers = {"coupling", "src"}
    tag = ".".join(parts[1:]) if parts[0] in known_wrappers and len(parts) > 1 else run_prefix
    return run_prefix, tag


def _build_nc_path(out_dir: Path, run_prefix: str, suffix: str) -> Path:
    """Prepend run_prefix to a suffix to get a full nc path.

    _build_nc_path(out_dir, "src.H.ssp370", "emuAIS.emulandice.AIS_localsl.nc")
    → out_dir / "src.H.ssp370.emuAIS.emulandice.AIS_localsl.nc"
    """
    return out_dir / f"{run_prefix}.{suffix}"


def _resolve_total_nc(out_dir: Path, run_prefix: str, wf: str, scale: str) -> Path:
    """Return the total workflow nc path, accepting both .local.nc and .localsl.nc naming.

    Some FACTS runs name the file ...wf1e.local.nc, others use ...wf1e.localsl.nc.
    Glob for both; return the first hit or the plain form as fallback.
    """
    hits = sorted(out_dir.glob(f"{run_prefix}.total.workflow.{wf}.{scale}*.nc"))
    return hits[0] if hits else out_dir / f"{run_prefix}.total.workflow.{wf}.{scale}.nc"


# ─────────────────────────────────────────────────────────
# Discovery helpers
# ─────────────────────────────────────────────────────────

def _count_nc_locations(out_dir: Path) -> int:
    """
    Return the number of tide gauge locations in the first available
    *.total.workflow.*.local.nc file found in out_dir.
    Used to prefer the output directory that has more locations (more complete run).
    Returns 0 if no suitable file exists or the file cannot be read.
    """
    candidates = sorted(out_dir.glob("*.total.workflow.*.local*.nc"))
    if not candidates:
        return 0
    try:
        ds = xr.open_dataset(candidates[0])
        n  = int(ds.locations.size)
        ds.close()
        return n
    except Exception:
        return 0


def collect_ssp_entries(exp_root: Path = None, ssp_dirs: list = None) -> list:
    """
    Returns a list of (ssp_tag, run_prefix, output_dir, exp_dir) tuples.

    The run_prefix is read directly from the actual NC filenames on disk —
    not inferred from the folder name. This makes the dashboard robust to any
    scenario naming convention (coupling.ssp*, rco.LL.nz, src.H.ssp370, rff.LL, etc.).

    Args:
        exp_root:  Root folder — scan all subdirectories for scenario output.
        ssp_dirs:  List of individual scenario folders (or their output/ subfolders).

    Returns:
        Sorted list of (ssp_tag, run_prefix, output_dir, exp_dir).
    """
    entries   = []
    seen_tags = set()

    def _try_add(exp_dir: Path, out_dir: Path):
        if not out_dir.is_dir():
            return
        nc_files = sorted(out_dir.glob("*.total.workflow.*.nc"))
        if not nc_files:
            return
        try:
            run_prefix, tag = _parse_run_prefix_and_tag(nc_files[0])
        except Exception as exc:
            log.warning("Could not parse run prefix in %s: %s", out_dir, exc)
            return
        if tag in seen_tags:
            log.warning("Scenario %s already added — skipping %s", tag, out_dir)
            return
        entries.append((tag, run_prefix, out_dir, exp_dir))
        seen_tags.add(tag)
        log.info("Found scenario %s (prefix=%s) in %s", tag, run_prefix, out_dir)

    if exp_root:
        for d in sorted(exp_root.iterdir()):
            if not d.is_dir():
                continue
            out = d / "output"
            if not (out.is_dir() and any(out.glob("*.total.workflow.*.nc"))):
                continue
            # If an "output copy" directory also exists, pick whichever has more
            # tide gauge locations in its local nc files.
            out_copy = d / "output copy"
            if out_copy.is_dir() and any(out_copy.glob("*.total.workflow.*.nc")):
                n_out  = _count_nc_locations(out)
                n_copy = _count_nc_locations(out_copy)
                if n_copy > n_out:
                    log.info("Preferring 'output copy' for %s (%d locs > %d locs in output/)",
                             d.name, n_copy, n_out)
                    out = out_copy
            _try_add(d, out)

    for raw in (ssp_dirs or []):
        p = Path(raw).resolve()
        if p.name == "output" and p.is_dir():
            out_dir, exp_dir = p, p.parent
        elif (p / "output").is_dir():
            out_dir, exp_dir = p / "output", p
        else:
            out_dir, exp_dir = p, p.parent
        if not out_dir.is_dir():
            log.warning("Directory not found — %s", out_dir)
            continue
        _try_add(exp_dir, out_dir)

    return sorted(entries, key=lambda e: e[0])


def discover_workflows(entries: list) -> list:
    """
    Discover all workflow IDs present in the output .nc filenames.

    Args:
        entries: List of (ssp_tag, run_prefix, output_dir, exp_dir) tuples.

    Returns:
        Sorted list of workflow ID strings (e.g. ["wf1e", "wf1f", ...]).
    """
    wfs = set()
    for _, _, out_dir, _ in entries:
        for f in out_dir.glob("*.total.workflow.*.nc"):
            parts = f.stem.split(".")
            for i, p in enumerate(parts):
                if p == "workflow" and i + 1 < len(parts):
                    c = parts[i + 1]
                    if c not in ("local", "global", "localsl", "globalsl"):
                        wfs.add(c)
    order = list(WF_LABELS.keys())
    return sorted(wfs, key=lambda w: order.index(w) if w in order else 99)


def load_location_list(entries: list) -> list:
    """
    Load tide gauge station list from location.lst in the first available exp_dir.

    Args:
        entries: List of (ssp_tag, run_prefix, output_dir, exp_dir) tuples.

    Returns:
        List of dicts with keys: name, id, lat, lon.
    """
    for _, _, _, exp_dir in entries:
        p = exp_dir / "location.lst"
        if p.exists():
            df = pd.read_csv(p, sep="\t", header=None, names=["name", "id", "lat", "lon"],
                             engine="python")
            log.info("Loaded %d locations from %s", len(df), p)
            return df.to_dict("records")
    log.warning("No location.lst found in any experiment directory")
    return []

# ─────────────────────────────────────────────────────────
# Loading + quantile computation
# ─────────────────────────────────────────────────────────

def compute_quantiles(nc_path: Path) -> dict:
    """
    Open a FACTS .nc file and compute p5/p17/p50/p83/p95 quantiles.

    Args:
        nc_path: Path to a sea_level_change .nc file.

    Returns:
        Dict with keys: years, locations, q (5×years×locs), lat, lon.

    Example:
        result = compute_quantiles(Path("coupling.ssp585.total.workflow.wf1e.local.nc"))
    """
    ds = xr.open_dataset(nc_path)
    if "sea_level_change" not in ds:
        raise KeyError(f"Variable 'sea_level_change' not found in {nc_path.name}")
    sl = ds["sea_level_change"].values          # shape: (samples, years, locations)
    q  = np.quantile(sl, QUANTILES, axis=0)    # collapse sample axis → shape: (5, years, locations)
    return {
        "years":     ds.years.values.tolist(),
        "locations": ds.locations.values.tolist(),
        "q":         q,   # q[0]=p05, q[1]=p17, q[2]=p50, q[3]=p83, q[4]=p95
        "lat":       ds["lat"].values.tolist() if "lat" in ds else [],
        "lon":       ds["lon"].values.tolist() if "lon" in ds else [],
    }


def compute_quantiles_sum(nc_paths: list) -> dict:
    """
    Sum sea_level_change arrays across multiple .nc files, then compute quantiles.
    Used for wf1f AIS local: EAIS_localsl + WAIS_localsl (no combined file exists).

    Args:
        nc_paths: List of Path objects to sum. All must share the same shape.

    Returns:
        Same dict format as compute_quantiles().
    """
    combined = None
    ref_ds   = None
    for path in nc_paths:
        ds = xr.open_dataset(path)
        if "sea_level_change" not in ds:
            raise KeyError(f"Variable 'sea_level_change' not found in {path.name}")
        sl = ds["sea_level_change"].values      # (samples, years, locations)
        if combined is None:
            combined = sl
            ref_ds   = ds
        else:
            combined = combined + sl
    q = np.quantile(combined, QUANTILES, axis=0)
    return {
        "years":     ref_ds.years.values.tolist(),
        "locations": ref_ds.locations.values.tolist(),
        "q":         q,
        "lat":       ref_ds["lat"].values.tolist() if "lat" in ref_ds else [],
        "lon":       ref_ds["lon"].values.tolist() if "lon" in ref_ds else [],
    }


def _store_result(data_dict, location_meta, result, key_prefix):
    """
    Store quantile results into data_dict and location_meta.

    Args:
        data_dict:     Dict being populated with {key: {years, med, lo, hi}}.
        location_meta: Dict being populated with {loc_id: {lat, lon}}.
        result:        Output of compute_quantiles().
        key_prefix:    String prefix for the key (everything before |{loc_id}).

    Example:
        _store_result(data_dict, location_meta, result, "ssp585|total|wf1e|local")
    """
    q    = result["q"]   # shape: (5, years, locations) — see QUANTILES index map above
    lats = result["lat"]
    lons = result["lon"]
    for li, loc_id in enumerate(result["locations"]):
        loc_id = int(loc_id)
        # Key format: "{ssp}|{component}|{wf}|{scale}|{loc_id}"
        # loc_id = -1 for global mean SL; positive int for tide gauge station
        key = f"{key_prefix}|{loc_id}"
        data_dict[key] = {
            "years": result["years"],
            "med":   _r1(q[2, :, li]),   # p50 — median projection
            "lo":    _r1(q[1, :, li]),   # p17 — lower likely range
            "hi":    _r1(q[3, :, li]),   # p83 — upper likely range
            "vlo":   _r1(q[0, :, li]),   # p05 — very likely lower bound
            "vhi":   _r1(q[4, :, li]),   # p95 — very likely upper bound
        }
        if loc_id not in location_meta:
            def _safe_coord(arr, idx):
                if not arr or idx >= len(arr):
                    return None
                v = float(arr[idx])
                return None if (np.isnan(v) or np.isinf(v)) else v
            location_meta[loc_id] = {
                "lat": _safe_coord(lats, li),
                "lon": _safe_coord(lons, li),
            }


def _infer_component_from_stem(stem: str) -> str:
    """
    Extract the sea-level component from a FACTS .nc filename stem.

    File pattern: coupling.sspXXX.module.model.COMPONENT_{scale}sl
    The component token sits immediately before _{scale}sl at the end.

    Matches against known component names first; falls back to the raw token.
    """
    last = stem.split(".")[-1]                       # e.g. "GrIS_globalsl"
    for suffix in ("_globalsl", "_localsl", "_global", "_local"):
        if last.lower().endswith(suffix):
            raw = last[: len(last) - len(suffix)]    # e.g. "GrIS"
            break
    else:
        raw = last

    # Normalise: strip sub-component prefix (e.g. "icesheets_AIS" → "AIS")
    for k in ("total", "AIS", "GrIS", "glaciers", "sterodynamics",
              "landwaterstorage", "vlm", "verticallandmotion"):
        if k.lower() in raw.lower():
            # Map known aliases
            return {
                "verticallandmotion": "vlm",
                "icesheets_AIS": "AIS", "icesheets_GIS": "GrIS",
                "GIS": "GrIS",
            }.get(raw, k)
    return raw   # unknown component — use as-is


def _infer_wf_from_stem(stem: str) -> str:
    """
    Heuristically map a FACTS filename stem to the closest known workflow ID.

    Uses the model/module tokens in the filename.  The mapping is approximate
    for multi-model workflows (wf2e/wf3e share emulandice for GrIS).
    """
    s = stem.lower()
    if "bamber19" in s:
        return "wf4"
    if "deconto21" in s:
        return "wf3e"
    if "larmip" in s:
        return "wf2e"
    if "fittedismip" in s:
        return "wf1f"
    if "ipccar5" in s:
        return "wf1f"
    # emulandice is used by wf1e, wf2e, wf3e — default to wf1e
    return "wf1e"


def _find_best_location_lst(nc_path: Path, loc_ids_in_file: list) -> dict:
    """
    Find the location.lst that covers the most location IDs present in the NC file.

    Searches:
      1. nc_path.parent         (same folder as the file)
      2. nc_path.parent.parent  (e.g. coupling.ssp585/)
      3. All coupling.ssp* sibling directories one level up (exp_root level)

    Picks the file with the most ID matches against loc_ids_in_file.
    This handles the case where the file's own SSP directory has a partial
    location.lst (e.g. only 1 station) while a sibling SSP directory has the
    full 24-station list.

    Returns:
        {int(loc_id): pandas row} for the best-matching file, or {} if none found.
    """
    target_ids = set(int(x) for x in loc_ids_in_file)
    candidates = []

    search_dirs = [nc_path.parent, nc_path.parent.parent]
    # Also scan all sibling scenario directories at exp_root level
    exp_root_candidate = nc_path.parent.parent.parent
    if exp_root_candidate.is_dir():
        for sibling in sorted(exp_root_candidate.iterdir()):
            if sibling.is_dir() and (sibling / "location.lst").exists():
                search_dirs.append(sibling)

    for d in search_dirs:
        lst = d / "location.lst"
        if not lst.exists():
            continue
        try:
            df = pd.read_csv(lst, sep="\t", header=None, names=["name", "id", "lat", "lon"])
            matched = len(set(int(x) for x in df["id"]) & target_ids)
            candidates.append((matched, lst, df))
        except Exception:
            pass

    if not candidates:
        return {}

    # Pick the candidate with the most matching IDs
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_match, best_lst, best_df = candidates[0]
    log.info("[single-nc] location.lst: %s  (%d / %d IDs matched)",
             best_lst, best_match, len(target_ids))
    return {int(row["id"]): row for _, row in best_df.iterrows()}


def load_single_nc(nc_path: Path) -> dict:
    """
    Load a single FACTS .nc file and return structures compatible with build_dashboard().

    Infers SSP, component, workflow, and scale from the filename, reads all
    tide gauge (or global) time series, computes 5 quantiles, and finds the
    best-matching location.lst by scanning sibling SSP directories.

    The COMPONENTS and COMPONENT_LABELS globals are narrowed to only the
    detected component so that all dashboard dropdowns and the component table
    only show the data that is actually present in the file.

    Returns:
        dict with keys: data_dict, years, locations, location_meta, ssps, wfs, comp

    Example:
        result = load_single_nc(Path("coupling.ssp585.emuGrIS.emulandice.GrIS_globalsl.nc"))
        build_dashboard(result["data_dict"], result["years"], result["locations"], ...)
    """
    stem  = nc_path.stem
    parts = stem.split(".")

    # ── Parse filename ───────────────────────────────────────
    ssp   = next((p for p in parts if re.match(r"ssp\d+", p, re.IGNORECASE)), "ssp_unknown")
    scale = "global" if "global" in stem.lower() else "local"
    comp  = _infer_component_from_stem(stem)
    wf    = _infer_wf_from_stem(stem)

    log.info("[single-nc] file      : %s", nc_path.name)
    log.info("[single-nc] SSP=%s  component=%s  workflow=%s  scale=%s", ssp, comp, wf, scale)

    # ── Narrow global COMPONENTS to only what this file provides ──
    # This fixes the component table and all dropdowns showing all 7 components
    # when only 1 has data.
    label = COMPONENT_LABELS.get(comp, comp)
    COMPONENTS[:] = [comp]            # in-place so all references see the change
    COMPONENT_LABELS.clear()
    COMPONENT_LABELS[comp] = label

    # ── Quantiles ────────────────────────────────────────────
    result  = compute_quantiles(nc_path)
    years   = result["years"]
    loc_ids = result["locations"]     # list of int location IDs from the file
    lats    = result["lat"]
    lons    = result["lon"]
    q       = result["q"]             # (5, n_years, n_locs)

    # ── Find best location.lst (searches sibling SSP dirs) ───
    loc_meta_from_lst = _find_best_location_lst(nc_path, loc_ids)

    # ── Build data_dict, locations, location_meta ────────────
    def _safe(v):
        try:
            return None if (v is None or np.isnan(v) or np.isinf(v)) else v
        except (TypeError, ValueError):
            return None

    data_dict:     dict = {}
    locations:     list = []
    location_meta: dict = {}

    for li, raw_lid in enumerate(loc_ids):
        loc_id = int(raw_lid)

        if loc_id in loc_meta_from_lst:
            row  = loc_meta_from_lst[loc_id]
            name = str(row["name"])
            lat  = float(row["lat"])
            lon  = float(row["lon"])
        else:
            name = "Global mean" if loc_id == -1 else f"ID {loc_id}"
            lat  = _safe(float(lats[li])) if li < len(lats) else None
            lon  = _safe(float(lons[li])) if li < len(lons) else None

        locations.append({"name": name, "id": loc_id, "lat": lat, "lon": lon})
        location_meta[loc_id] = {"lat": _safe(lat), "lon": _safe(lon)}

        key = f"{ssp}|{comp}|{wf}|{scale}|{loc_id}"
        data_dict[key] = {
            "years": years,
            "vlo":   _r1(q[0, :, li]),
            "lo":    _r1(q[1, :, li]),
            "med":   _r1(q[2, :, li]),
            "hi":    _r1(q[3, :, li]),
            "vhi":   _r1(q[4, :, li]),
        }

    log.info("[single-nc] Loaded %d location(s), %d time steps", len(loc_ids), len(years))
    return {
        "data_dict":     data_dict,
        "years":         years,
        "locations":     locations,
        "location_meta": location_meta,
        "ssps":          [ssp],
        "wfs":           [wf],
        "comp":          comp,
    }


def load_confidence_files(conf_root: Path,
                          confidence_level: "str | list[str]" = "medium_confidence",
                          location_lst: Path = None) -> dict:
    """
    Load AR6-style pre-computed confidence level NC files.

    Expected structure:
        conf_root/{confidence_level}/{ssp}/{component}_{ssp}_{confidence_level}_values.nc

    Unlike standard FACTS .nc files (which have a samples axis that must be reduced),
    these files store pre-computed quantiles directly:
        sea_level_change shape: (quantiles=107, years, locations)

    Quantile indices used: p05=7, p17=20, p50=53, p83=86, p95=99

    Workflow tags:
        - Single level  → "conf"      (backward compatible)
        - Both levels   → "med_conf" / "low_conf"  (lets slots show each independently)

    Args:
        conf_root:        Root of confidence file tree (contains low_confidence/, medium_confidence/).
        confidence_level: Sub-directory to use: "medium_confidence", "low_confidence", or
                          a list of both (e.g. ["medium_confidence", "low_confidence"]).
                          Pass "both" as a shortcut to load both directories.

    Returns:
        dict with keys: data_dict, years, locations, location_meta, ssps, wfs
    """
    # Normalise to a list
    if confidence_level == "both":
        levels = ["medium_confidence", "low_confidence"]
    elif isinstance(confidence_level, str):
        levels = [confidence_level]
    else:
        levels = list(confidence_level)

    # Workflow tag: single level keeps "conf" for backward compat; multiple → distinct tags
    _LEVEL_WF = {
        "medium_confidence": "med_conf",
        "low_confidence":    "low_conf",
    }
    data_dict:     dict = {}
    location_meta: dict = {}
    locations_seen: dict = {}   # loc_id → {name, id, lat, lon}
    years_ref = None
    ssps_found: set = set()
    wfs_found:  list = []

    for level in levels:
        conf_dir = conf_root / level
        if not conf_dir.is_dir():
            raise FileNotFoundError(f"Confidence level directory not found: {conf_dir}")

        wf_tag = _LEVEL_WF.get(level, "conf")
        if wf_tag not in wfs_found:
            wfs_found.append(wf_tag)

        for ssp_dir in sorted(conf_dir.iterdir()):
            if not ssp_dir.is_dir():
                continue
            ssp_tag = ssp_dir.name   # e.g. "ssp585"

            for nc_path in sorted(ssp_dir.glob("*_values.nc")):
                # Filename: {component}_{ssp}_{confidence_level}_values.nc
                # First underscore-delimited token is the component name.
                raw_comp = nc_path.stem.split("_")[0]
                comp = _CONF_COMP_MAP.get(raw_comp, raw_comp)

                try:
                    ds  = xr.open_dataset(nc_path)
                    sl  = ds["sea_level_change"].values   # (quantiles, years, locations)
                    yrs = ds.years.values.tolist()
                    lids = ds.locations.values.tolist()
                    lats = ds["lat"].values.tolist() if "lat" in ds else []
                    lons = ds["lon"].values.tolist() if "lon" in ds else []
                    ds.close()
                except Exception as exc:
                    log.warning("Failed to load confidence file %s: %s", nc_path.name, exc)
                    continue

                if years_ref is None:
                    years_ref = yrs
                ssps_found.add(ssp_tag)

                for li, raw_lid in enumerate(lids):
                    loc_id = int(raw_lid)
                    key = f"{ssp_tag}|{comp}|{wf_tag}|local|{loc_id}"
                    data_dict[key] = {
                        "years": yrs,
                        "vlo":   _r1(sl[_CONF_Q_IDX["vlo"], :, li]),
                        "lo":    _r1(sl[_CONF_Q_IDX["lo"],  :, li]),
                        "med":   _r1(sl[_CONF_Q_IDX["med"], :, li]),
                        "hi":    _r1(sl[_CONF_Q_IDX["hi"],  :, li]),
                        "vhi":   _r1(sl[_CONF_Q_IDX["vhi"], :, li]),
                    }
                    if loc_id not in locations_seen:
                        lat = float(lats[li]) if li < len(lats) else None
                        lon = float(lons[li]) if li < len(lons) else None
                        locations_seen[loc_id] = {
                            "name": f"ID {loc_id}",
                            "id":   loc_id,
                            "lat":  lat,
                            "lon":  lon,
                        }
                        location_meta[loc_id] = {"lat": lat, "lon": lon}

                log.info("[%s] Loaded %s | %s | %s", wf_tag, ssp_tag, comp, nc_path.name)

    if not data_dict:
        raise RuntimeError(f"No confidence data loaded from {conf_dir}")

    # Try to resolve location names from a location.lst file.
    # Priority: explicit --location-lst flag → auto-search near conf_root.
    lst_map: dict = {}
    candidates = []
    if location_lst is not None:
        candidates = [location_lst]
    else:
        search_dirs = [conf_root, conf_root.parent, conf_root.parent.parent,
                       conf_root.parent.parent.parent]
        candidates = [d / "location.lst" for d in search_dirs]
    for lst in candidates:
        if lst and lst.exists():
            try:
                df = pd.read_csv(lst, sep="\t", header=None, names=["name", "id", "lat", "lon"])
                lst_map = {int(r["id"]): str(r["name"]) for _, r in df.iterrows()}
                log.info("[conf] Resolved location names from %s", lst)
                break
            except Exception:
                pass
    for loc_id, loc_info in locations_seen.items():
        if loc_id in lst_map:
            loc_info["name"] = lst_map[loc_id]

    locations = sorted(locations_seen.values(), key=lambda x: x["id"])
    ssps = sorted(ssps_found, key=lambda s: list(SSP_COLORS.keys()).index(s) if s in SSP_COLORS else 99)

    log.info("[conf] %d data series | %d SSPs | %d location(s) | workflows: %s",
             len(data_dict), len(ssps), len(locations), wfs_found)
    return {
        "data_dict":     data_dict,
        "years":         years_ref or [],
        "locations":     locations,
        "location_meta": location_meta,
        "ssps":          ssps,
        "wfs":           wfs_found,
    }


def precompute_all(entries: list, wfs: list) -> tuple:
    """
    Load all total + component .nc files and compute quantiles.

    Data dict keys:
      total     → "{ssp}|total|{wf}|{scale}|{loc_id}"
      component → "{ssp}|{component}|{wf}|{scale}|{loc_id}"
                  (same data stored under every wf so JS lookup is uniform)

    Args:
        entries: List of (ssp_tag, output_dir, exp_dir) tuples.
        wfs:     List of workflow IDs.

    Returns:
        (data_dict, years_ref, location_meta)

    Example:
        data_dict, years, loc_meta = precompute_all(entries, wfs)
    """
    data_dict     = {}
    location_meta = {}
    years_ref     = None

    # ── Total workflow files ───────────────────────────────
    total_combos = [
        (ssp, run_prefix, out_dir, wf, sc)
        for ssp, run_prefix, out_dir, _ in entries
        for wf in wfs
        for sc in ("local", "global")
    ]
    log.info("Loading total workflow files (%d combinations) ...", len(total_combos))
    for i, (ssp, run_prefix, out_dir, wf, scale) in enumerate(total_combos):
        nc_path = _resolve_total_nc(out_dir, run_prefix, wf, scale)
        log.debug("[%3d/%d] %s", i + 1, len(total_combos), nc_path.name)
        if not nc_path.exists():
            log.debug("  Not found — skipping")
            continue
        try:
            result = compute_quantiles(nc_path)
        except Exception as exc:
            log.warning("Failed to load %s: %s", nc_path.name, exc)
            continue
        if years_ref is None or len(result["years"]) > len(years_ref):
            years_ref = result["years"]
        _store_result(data_dict, location_meta, result, f"{ssp}|total|{wf}|{scale}")

    # ── Workflow-specific components (AIS, GrIS, glaciers) ─
    log.info("Loading workflow-specific component files ...")
    for ssp, run_prefix, out_dir, _ in entries:
        for wf in wfs:
            for comp, pattern in WORKFLOW_COMPONENT_FILES.get(wf, {}).items():
                for scale in ("local", "global"):
                    nc_path = _build_nc_path(out_dir, run_prefix, pattern.format(scale=scale))
                    log.debug("  %s  %s  %s  %s", wf, comp, scale, nc_path.name)
                    if not nc_path.exists():
                        # Check for a fallback sum (e.g. wf1f AIS local = EAIS + WAIS)
                        fallback = (WORKFLOW_COMPONENT_FALLBACK_SUM
                                    .get(wf, {}).get(comp, {}).get(scale))
                        if fallback:
                            fb_paths = [_build_nc_path(out_dir, run_prefix, p.format(scale=scale))
                                        for p in fallback]
                            if all(p.exists() for p in fb_paths):
                                log.debug("  Fallback sum: %s", [p.name for p in fb_paths])
                                try:
                                    result = compute_quantiles_sum(fb_paths)
                                except Exception as exc:
                                    log.warning("Failed fallback sum %s|%s|%s|%s: %s",
                                                ssp, comp, wf, scale, exc)
                                    continue
                            else:
                                log.debug("  Not found and fallback incomplete — skipping")
                                continue
                        else:
                            log.debug("  Not found — skipping")
                            continue
                    else:
                        try:
                            result = compute_quantiles(nc_path)
                        except Exception as exc:
                            log.warning("Failed to load %s: %s", nc_path.name, exc)
                            continue
                    if years_ref is None or len(result["years"]) > len(years_ref):
                        years_ref = result["years"]
                    _store_result(data_dict, location_meta, result, f"{ssp}|{comp}|{wf}|{scale}")

    # ── Workflow-independent components (sterodynamics, lws, vlm) ─
    log.info("Loading workflow-independent component files ...")
    for ssp, run_prefix, out_dir, _ in entries:
        for comp, pattern in WORKFLOW_INDEPENDENT_COMPONENTS.items():
            for scale in ("local", "global"):
                nc_path = _build_nc_path(out_dir, run_prefix, pattern.format(scale=scale))
                log.debug("  %s  %s  %s", comp, scale, nc_path.name)
                if not nc_path.exists():
                    log.debug("  Not found — skipping")
                    continue
                try:
                    result = compute_quantiles(nc_path)
                except Exception as exc:
                    log.warning("Failed to load %s: %s", nc_path.name, exc)
                    continue
                if years_ref is None or len(result["years"]) > len(years_ref):
                    years_ref = result["years"]
                # Fan-out: store the same result under every workflow key.
                # Sterodynamics/LWS/VLM are workflow-independent, but the JS lookup
                # always uses the full key "{ssp}|{comp}|{wf}|{scale}|{loc_id}".
                # Duplicating the data under each wf keeps the key format uniform
                # and avoids special-casing in the browser callback.
                for wf in wfs:
                    _store_result(data_dict, location_meta, result, f"{ssp}|{comp}|{wf}|{scale}")

    log.info("Loaded %d data series total.", len(data_dict))
    return data_dict, years_ref or [], location_meta

# ─────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────

def _color_box_html(color: str) -> str:
    return (
        f'<div style="display:inline-block;width:18px;height:18px;'
        f'background-color:{color};border:1px solid #444;border-radius:3px;'
        f'margin-top:6px;"></div>'
    )

_STYLE_PREVIEW = {
    "solid":    "────",
    "dashed":   "— — —",
    "dotted":   "⋅ ⋅ ⋅ ⋅",
    "circle":   "○ ○ ○ ○",
    "diamond":  "◇ ◇ ◇ ◇",
    "asterisk": "* * * *",
    "triangle": "▲ ▲ ▲ ▲",
}

def _style_box_html(style: str) -> str:
    preview = _STYLE_PREVIEW.get(style, "────")
    return f'<span style="font-family:monospace;font-size:14px;">{preview}</span>'


def _loc_info_html(loc_id: int, name: str, lat, lon) -> str:
    lat_txt = "NA" if lat is None else f"{lat:.3f}"
    lon_txt = "NA" if lon is None else f"{lon:.3f}"
    return (
        f"<div style='font-size:11px;line-height:1.5;'>"
        f"<b>Location {loc_id}</b><br>"
        f"<b>{name}</b><br>"
        f"lat: {lat_txt} &nbsp; lon: {lon_txt}"
        f"</div>"
    )


def _workflow_table_html() -> str:
    """Return the workflow reference table as inline HTML (Kopp et al. 2023, Table 2)."""
    th = "style='padding:5px 14px 5px 0;text-align:left;border-bottom:2px solid #555;'"
    td = "style='padding:4px 14px 4px 0;font-family:monospace;font-size:12px;'"
    hd = "style='padding:5px 0 3px 0;font-style:italic;color:#555;border-top:1px solid #ccc;border-bottom:1px solid #ccc;'"
    rows_medium = [
        ("1e", "emulandice", "emulandice",  "emulandice",       "ssp", "tlm"),
        ("1f", "FittedISMIP","ipccar5",     "ipccar5 (GMIP2)",  "ssp", "tlm"),
        ("2e", "emulandice", "larmip",      "emulandice",       "ssp", "tlm"),
        ("2f", "FittedISMIP","larmip",      "ipccar5 (GMIP2)",  "ssp", "tlm"),
    ]
    rows_low = [
        ("3e", "emulandice", "deconto21",   "emulandice",       "ssp", "tlm"),
        ("3f", "FittedISMIP","deconto21",   "ipccar5 (GMIP2)",  "ssp", "tlm"),
        ("4",  "bamber19",   "bamber19",    "ipccar5 (GMIP2)",  "ssp", "tlm"),
    ]
    def make_rows(data):
        out = []
        for r in data:
            cells = "".join(f"<td {td}>{v}</td>" for v in r)
            out.append(f"<tr>{cells}</tr>")
        return "\n".join(out)
    return f"""
<div style="margin-top:16px;">
  <b>Workflows</b> as defined in <b>Table 2</b> of
  <a href="https://doi.org/10.5194/gmd-16-7461-2023">Kopp et al. (2023) FACTS GMD</a>
  and match those of AR6
  <a href="https://doi.org/10.1017/9781009157896.011">(Fox-Kemper et al., 2021)</a>.
  <table style="border-collapse:collapse;margin-top:8px;font-size:13px;">
    <thead>
      <tr>
        <th {th}>Workflow</th>
        <th {th}>GrIS</th>
        <th {th}>AIS</th>
        <th {th}>Glaciers</th>
        <th {th}>Land water</th>
        <th {th}>Sterodynamic</th>
      </tr>
    </thead>
    <tbody>
      <tr><td colspan="6" {hd}>&nbsp;Medium-confidence workflows</td></tr>
      {make_rows(rows_medium)}
      <tr><td colspan="6" {hd}>&nbsp;Low-confidence workflows</td></tr>
      {make_rows(rows_low)}
    </tbody>
  </table>
</div>
"""


# ─────────────────────────────────────────────────────────
# Component breakdown table (rows = components, cols = SSPs)
# ─────────────────────────────────────────────────────────

def _build_component_table_section(
    data_dict:        dict,
    years:            list,
    ssps:             list,
    wfs:              list,
    loc_options_all:  list,
    location_meta_js: dict,
    unit_sel:         object = None,
) -> object:
    """
    Build the interactive component breakdown TABLE (Bokeh DataTable).

    Rows = sea-level components, columns = SSPs.
    Each cell: median / (p17, p83) / [p05, p95] for selected workflow,
    year, scale, and location.  Mirrors facts.plotting.dashboard.table.html
    but supports both Global Mean SL and Indian tide gauge (Local RSL).

    Args:
        data_dict:        Full data dict keyed by {ssp}|{component}|{wf}|{scale}|{loc_id}.
        years:            Full year list.
        ssps:             List of SSP tag strings.
        wfs:              List of workflow ID strings.
        loc_options_all:  (value, label) pairs for the location Select widget.
        location_meta_js: JS-side location metadata dict.

    Returns:
        Bokeh Column layout containing the component table.

    Example:
        tbl = _build_component_table_section(data_dict, years, ssps, wfs, loc_opts, loc_meta)
    """
    default_wf       = wfs[0]
    default_year_int = 2100
    comps = COMPONENTS      # [total, AIS, GrIS, glaciers, sterodynamics, landwaterstorage, vlm]

    # Confidence files only have "local" keys — no global-mean variant exists.
    # Detect this by checking whether any "global" key is present in data_dict.
    has_global = any("|global|" in k for k in data_dict)
    if has_global:
        default_scale   = "global"
        default_loc_int = -1   # global mean SL
    else:
        # Confidence mode: force "local" and use the first real location id.
        default_scale = "local"
        default_loc_int = int(loc_options_all[0][0]) if loc_options_all else -1

    # Pre-populate for default selections
    init_data = {"component": list(comps)}
    for ssp in ssps:
        init_data[ssp] = []
    for comp in comps:
        for ssp in ssps:
            key = f"{ssp}|{comp}|{default_wf}|{default_scale}|{default_loc_int}"
            d   = data_dict.get(key)
            if not d:
                init_data[ssp].append("")
                continue
            try:
                idx = d["years"].index(default_year_int)
            except ValueError:
                init_data[ssp].append("")
                continue
            med = d["med"][idx]; lo = d["lo"][idx]; hi = d["hi"][idx]
            vlo = d["vlo"][idx]; vhi = d["vhi"][idx]
            init_data[ssp].append(f"{med:.1f}\n({lo:.1f}, {hi:.1f})\n[{vlo:.1f}, {vhi:.1f}]")

    source_comp = ColumnDataSource(data=init_data)

    # ── TableColumns ──────────────────────────────────────
    html_fmt = HTMLTemplateFormatter(template='<div style="white-space:pre-line;"><%= value %></div>')
    tbl_columns = [
        TableColumn(
            field="component", title="Component",
            formatter=HTMLTemplateFormatter(
                template='<div style="font-weight:bold;font-family:monospace;"><%= value %></div>'
            ), width=150,
        ),
    ]
    for ssp in ssps:
        tbl_columns.append(TableColumn(
            field=ssp, title=SSP_LABELS.get(ssp, ssp), formatter=html_fmt, width=185,
        ))

    data_table = DataTable(
        source=source_comp,
        columns=tbl_columns,
        width=900,
        height=min(600, 80 + 80 * len(comps)),
        row_height=80,
        index_position=None,
        editable=False,
    )

    # ── Controls ──────────────────────────────────────────
    year_opts    = [str(y) for y in sorted(set(years))]
    default_year = str(default_year_int) if str(default_year_int) in year_opts else year_opts[-1]
    wf_opts      = [(wf, WF_LABELS.get(wf, wf)) for wf in wfs]

    wf_sel   = Select(title="Workflow",         value=default_wf,    options=wf_opts,   width=220)
    year_sel = Select(title="Year",             value=default_year,  options=year_opts, width=120)
    scale_sel= Select(title="Scale",            value=default_scale,
                      options=[("global","Global Mean SL"), ("local","Local RSL")], width=160)
    # In confidence mode the location dropdown starts at the first real location;
    # in global mode it starts at the placeholder "-1" entry.
    loc_default_str = str(default_loc_int)
    if not has_global and loc_options_all:
        loc_default_str = loc_options_all[0][0]
    loc_sel  = Select(title="Location (local)", value=loc_default_str,
                      options=loc_options_all, width=280)

    # Search bar: hidden until toggle is clicked.
    loc_search_comp = TextInput(placeholder="Search location...", width=280, visible=False)
    loc_search_comp.js_on_change("value", CustomJS(
        args=dict(loc_sel=loc_sel, all_opts=loc_options_all),
        code="""
        const q = cb_obj.value.trim().toLowerCase();
        const new_opts = q === ""
            ? all_opts.slice()
            : all_opts.filter(([v, l]) => l.toLowerCase().includes(q));
        if (new_opts.length > 0) {
            loc_sel.options = new_opts;
            if (!new_opts.some(([v]) => v === loc_sel.value)) {
                loc_sel.value = new_opts[0][0];
            }
        }
        """,
    ))

    loc_toggle_comp = Toggle(
        label="Search ▼  location",
        active=False,
        button_type="light",
        width=280,
    )
    loc_toggle_comp.js_on_change("active", CustomJS(
        args=dict(search=loc_search_comp, btn=loc_toggle_comp),
        code="""
        search.visible = btn.active;
        btn.label = btn.active ? 'Search ▲  location' : 'Search ▼  location';
        """,
    ))

    # ── CustomJS callback ─────────────────────────────────
    # Key format: "{ssp}|{component}|{wf}|{scale}|{loc_id}"
    # This table iterates over comps (rows) and ssps (columns) for a fixed workflow.
    # Workflow-independent components (sterodynamics, lws, vlm) are stored under every
    # wf key in Python, so the JS lookup is the same regardless of selected workflow.
    JS_COMP = """
    const wf_val    = wf_sel.value;
    const year_val  = parseInt(year_sel.value);
    const scale_val = scale_sel.value;
    // Global SL uses loc_id=-1 (only one location in global .nc files)
    const loc_val   = (scale_val === "global") ? -1 : parseInt(loc_sel.value);

    const uf_map = {"mm": 1.0, "cm": 0.1, "m": 0.001};
    const uf = uf_map[unit_sel.value] || 1.0;
    const dp_map = {"mm": 1, "cm": 2, "m": 4};
    const dp = dp_map[unit_sel.value] || 1;

    const new_data = { component: comps.slice() };
    for (let j = 0; j < ssps.length; j++) { new_data[ssps[j]] = []; }

    for (let i = 0; i < comps.length; i++) {
        const comp = comps[i];
        for (let j = 0; j < ssps.length; j++) {
            const ssp = ssps[j];
            const key = ssp + "|" + comp + "|" + wf_val + "|" + scale_val + "|" + loc_val;
            const d   = window.FACTS_DATA[key];
            if (!d) { new_data[ssp].push(""); continue; }
            const idx = d.years.indexOf(year_val);
            if (idx === -1) { new_data[ssp].push(""); continue; }
            const med = d.med[idx] * uf, lo = d.lo[idx] * uf, hi = d.hi[idx] * uf;
            const vlo_raw = (d.vlo !== undefined) ? d.vlo[idx] : null;
            const vhi_raw = (d.vhi !== undefined) ? d.vhi[idx] : null;
            const vlo = vlo_raw !== null ? vlo_raw * uf : null;
            const vhi = vhi_raw !== null ? vhi_raw * uf : null;
            let cell = med.toFixed(dp) + "\\n(" + lo.toFixed(dp) + ", " + hi.toFixed(dp) + ")";
            if (vlo !== null && vhi !== null) {
                cell += "\\n[" + vlo.toFixed(dp) + ", " + vhi.toFixed(dp) + "]";
            }
            new_data[ssp].push(cell);
        }
    }
    source_comp.data = new_data;
    source_comp.change.emit();
    """

    cb = CustomJS(
        args=dict(
            source_comp=source_comp,
            wf_sel=wf_sel, year_sel=year_sel,
            scale_sel=scale_sel, loc_sel=loc_sel,
            ssps=ssps, comps=comps,
            unit_sel=unit_sel,
        ),
        code=JS_COMP,
    )
    wf_sel.js_on_change("value",    cb)
    year_sel.js_on_change("value",  cb)
    scale_sel.js_on_change("value", cb)
    loc_sel.js_on_change("value",   cb)
    unit_sel.js_on_change("value",  cb)

    comp_head = Div(text="""
<div style="margin-top:32px;margin-bottom:6px;">
  <u>FACTS <b>sea-level projections — by component</b></u> (TABLE)<br>
  Select a <b>workflow</b>, <b>year</b>, <b>scale</b>, and <b>location</b> to view
  <u>median</u>, <u>(17th, 83rd)</u>, and <u>[5th, 95th]</u> percentile values
  for each sea-level component and SSP.
  &nbsp; Scale: Global Mean SL uses loc&nbsp;=&nbsp;−1; Local RSL uses the selected tide gauge.
</div>
""", width=900)

    return column(comp_head, row(wf_sel, year_sel, scale_sel, column(loc_toggle_comp, loc_search_comp, loc_sel)), data_table)


def _build_stacked_bar_section(
    data_dict:        dict,
    years:            list,
    ssps:             list,
    wfs:              list,
    loc_options_all:  list,
    location_meta_js: dict,
    unit_sel:         object = None,
) -> object:
    """
    Build the grouped bar chart section.

    X-axis  = all tide gauge locations; within each group one bar per SSP scenario
    Y-axis  = RSL (mm) at selected quantile, workflow, component, scale, year
    Colors  = one colour per SSP (consistent with line plot palette)

    Controls: workflow, component, scale, year, quantile.
    HoverTool shows location name, coords, SSP label, and value.
    """
    SSP_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
    plot_ssps = [s for s in SSP_ORDER if s in ssps] + [s for s in ssps if s not in SSP_ORDER]
    n_ssps    = len(plot_ssps)

    # -- Local locations only --
    local_locs = [(lid, lbl) for lid, lbl in loc_options_all if int(lid) >= 0]
    loc_ids    = [int(lid) for lid, _ in local_locs]
    loc_names  = [
        location_meta_js.get(str(lid), {}).get("name", str(lid))
        for lid in loc_ids
    ]
    loc_lat = [
        f"{location_meta_js[str(lid)]['lat']:.3f}"
        if location_meta_js.get(str(lid), {}).get("lat") is not None else "N/A"
        for lid in loc_ids
    ]
    loc_lon = [
        f"{location_meta_js[str(lid)]['lon']:.3f}"
        if location_meta_js.get(str(lid), {}).get("lon") is not None else "N/A"
        for lid in loc_ids
    ]
    n_locs = len(loc_ids)

    # -- Defaults --
    default_wf       = wfs[0]
    default_comp     = "total"
    default_scale    = "local"
    default_q_key    = "med"
    year_opts        = [str(y) for y in sorted(set(years))]
    default_year_str = "2100" if "2100" in year_opts else year_opts[-1]
    default_year     = int(default_year_str)

    # -- Grouped bar x-positions --
    # Group centers are integer indices [0, 1, 2, ..., n_locs-1] so that
    # major_label_overrides always uses exact integer keys — avoids float
    # key mismatch when JS updates ticks after SSP filtering.
    # Bars sit at +/- bar_w offsets around each integer group center.
    bar_w      = min(0.15, 0.8 / max(n_ssps, 1))
    half_group = (n_ssps * bar_w) / 2.0

    def _bar_x(loc_idx, ssp_idx):
        return loc_idx + ssp_idx * bar_w - half_group + bar_w / 2.0

    group_centers = list(range(n_locs))

    # -- Helper: fetch one value from data_dict --
    def _val(ssp, comp, wf, scale, loc_id, year, q_key):
        lookup = -1 if scale == "global" else loc_id
        d = data_dict.get(f"{ssp}|{comp}|{wf}|{scale}|{lookup}")
        if not d:
            return 0.0
        try:
            return d[q_key][d["years"].index(year)]
        except (ValueError, KeyError):
            return 0.0

    # -- Build flat per-bar arrays for ColumnDataSource --
    def _build_arrays(comp, wf, scale, year, q_key):
        xs, ys, colors, ssp_lbls, lnames, lids, llat, llon = [], [], [], [], [], [], [], []
        for li, loc_id in enumerate(loc_ids):
            for si, ssp in enumerate(plot_ssps):
                xs.append(_bar_x(li, si))
                ys.append(_val(ssp, comp, wf, scale, loc_id, year, q_key))
                colors.append(SSP_COLORS.get(ssp, _FALLBACK_COLORS[si % len(_FALLBACK_COLORS)]))
                ssp_lbls.append(SSP_LABELS.get(ssp, ssp))
                lnames.append(loc_names[li])
                lids.append(str(loc_id))
                llat.append(loc_lat[li])
                llon.append(loc_lon[li])
        return dict(
            x=xs, y=ys, colors=colors,
            ssp_labels=ssp_lbls, loc_names=lnames,
            loc_ids=lids, loc_lat=llat, loc_lon=llon,
        )

    # Start empty — bar chart is blank until user adds locations via the search panel
    init_data  = dict(x=[], y=[], colors=[], ssp_labels=[], loc_names=[], loc_ids=[], loc_lat=[], loc_lon=[])
    source_bar = ColumnDataSource(data=init_data)

    # -- Figure --
    p_bar = figure(
        x_range=(-0.6, 0.4),   # JS_BAR expands this as locations are added
        width=1200,
        height=520,
        title=(
            f"RSL Projections at {default_year} — Scenario Comparison per Tide Gauge"
            f"  ({default_wf}, {default_comp}, {default_scale}, median)"
        ),
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        y_axis_label="RSL Change (mm)",
        x_axis_label="Tide Gauge",
    )

    hover = HoverTool(tooltips=[
        ("Location", "@loc_names"),
        ("Scenario", "@ssp_labels"),
        ("Value",    "@y{0.1f} mm"),
        ("Lat",      "@loc_lat"),
        ("Lon",      "@loc_lon"),
    ])
    p_bar.add_tools(hover)

    p_bar.vbar(x="x", top="y", width=bar_w * 0.9, color="colors",
               source=source_bar, line_color="white", line_width=0.5)

    # x-axis: FixedTicker with integer positions + FuncTickFormatter backed by a CDS.
    # Updating label_cds from JS triggers a reactive re-render — unlike major_label_overrides
    # which does NOT reliably update after JS assignment in Bokeh's model system.
    x_ticker = FixedTicker(ticks=group_centers)
    label_cds = ColumnDataSource(data=dict(pos=list(range(n_locs)), name=loc_names[:]))
    label_fmt = CustomJSTickFormatter(
        args=dict(lsrc=label_cds),
        code="""
        const pos_arr = lsrc.data['pos'];
        const name_arr = lsrc.data['name'];
        for (let i = 0; i < pos_arr.length; i++) {
            if (pos_arr[i] === tick) return name_arr[i];
        }
        return '';
        """,
    )
    p_bar.xaxis.ticker    = x_ticker
    p_bar.xaxis.formatter = label_fmt
    p_bar.xaxis.major_label_orientation = 1.0

    # -- Legend: one entry per SSP (manual, outside plot) --
    legend_items = []
    for si, ssp in enumerate(plot_ssps):
        color = SSP_COLORS.get(ssp, _FALLBACK_COLORS[si % len(_FALLBACK_COLORS)])
        dummy_src = ColumnDataSource(data=dict(x=[0], y=[0]))
        dummy_r   = p_bar.vbar(x="x", top="y", width=bar_w, color=color,
                               source=dummy_src, visible=False)
        legend_items.append(LegendItem(label=SSP_LABELS.get(ssp, ssp), renderers=[dummy_r]))
    legend = Legend(items=legend_items, title="Scenario",
                    title_text_font_style="bold", label_text_font_size="12px",
                    click_policy="hide", spacing=6)
    p_bar.add_layout(legend, "right")

    # -- Controls --
    wf_opts   = [(wf, WF_LABELS.get(wf, wf)) for wf in wfs]
    comp_opts = [(c, c) for c in COMPONENTS]
    q_opts    = [
        ("vlo", "5th percentile"),
        ("lo",  "17th percentile"),
        ("med", "Median (50th)"),
        ("hi",  "83rd percentile"),
        ("vhi", "95th percentile"),
    ]

    wf_sel    = Select(title="Workflow:",   value=default_wf,    options=wf_opts,   width=240)
    comp_sel  = Select(title="Component:",  value=default_comp,  options=comp_opts, width=180)
    scale_sel = Select(
        title="Scale:", value=default_scale,
        options=[("local", "Local RSL"), ("global", "Global Mean SL")], width=160,
    )
    year_sel  = Select(title="Year:",       value=default_year_str, options=year_opts, width=120)
    q_sel     = Select(title="Quantile:",   value="med",          options=q_opts,    width=180)

    # -- SSP CheckboxGroup: user picks which SSPs to display --
    chk_ssp = CheckboxGroup(
        labels=[SSP_LABELS.get(s, s) for s in plot_ssps],
        active=list(range(n_ssps)),
        width=600,
    )

    # -- Location panel: Toggle button reveals a search bar + CheckboxGroup.
    #
    # UX: selected locations are always pinned to the top of the list (checked).
    # Unselected locations appear below, filtered by the search query.
    # Searching and checking a location adds it to the pinned top section.
    # Clearing the search keeps previously pinned locations selected at the top.
    #
    # Data sources:
    #   selected_src   — original indices of the currently selected (pinned) locations
    #   loc_filter_src — maps current CheckboxGroup display index → original index (for JS_BAR)
    #   guard_src      — re-entry guard: prevents circular callbacks when we rebuild the list
    all_loc_labels = [f"{loc_names[i]}  (ID: {lid})" for i, lid in enumerate(loc_ids)]
    selected_src   = ColumnDataSource(data={"orig_idx": []})
    loc_filter_src = ColumnDataSource(data={"orig_idx": list(range(n_locs))})
    guard_src      = ColumnDataSource(data={"busy": [0]})

    chk_loc = CheckboxGroup(
        labels=list(all_loc_labels),
        active=[],       # start empty — user adds locations via search
        width=340,
        visible=False,
        stylesheets=[InlineStyleSheet(css="""
            :host { max-height: 280px; overflow-y: auto;
                    display: block; border: 1px solid #ddd;
                    border-radius: 4px; padding: 4px; }
        """)],
    )
    loc_search = TextInput(placeholder="Search locations...", width=280, visible=False)
    loc_toggle = Toggle(
        label="Locations ▼  (0 selected)",
        active=False, button_type="light", width=220,
    )

    # Shared rebuild snippet: reads selected_src + current search query, then:
    #   1. Pins selected items to the top (always visible, checked)
    #   2. Shows unselected items that match the search below
    #   3. Updates loc_filter_src so JS_BAR always gets correct original indices
    # guard_src prevents this from re-triggering the active callback recursively.
    _JS_REBUILD = """
    const q_val    = loc_search.value.trim().toLowerCase();
    const sel_orig = selected_src.data.orig_idx.slice();
    const sel_set  = new Set(sel_orig);
    const n_sel    = sel_orig.length;

    const top_labels = sel_orig.map(i => all_labels[i]);
    const top_orig   = sel_orig.slice();
    const bot_labels = [], bot_orig = [];
    for (let i = 0; i < all_labels.length; i++) {
        if (!sel_set.has(i) && (q_val === "" || all_labels[i].toLowerCase().includes(q_val))) {
            bot_labels.push(all_labels[i]);
            bot_orig.push(i);
        }
    }

    guard_src.data = {"busy": [1]};
    chk_loc.labels = top_labels.concat(bot_labels);
    chk_loc.active = Array.from({length: n_sel}, (_, i) => i);
    loc_filter_src.data = {"orig_idx": top_orig.concat(bot_orig)};
    loc_filter_src.change.emit();
    guard_src.data = {"busy": [0]};

    const arrow = btn.active ? '▲' : '▼';
    btn.label = 'Locations ' + arrow + '  (' + n_sel + ' selected)';
    """

    loc_toggle.js_on_change("active", CustomJS(
        args=dict(panel=chk_loc, search=loc_search, btn=loc_toggle),
        code="""
        panel.visible = btn.active;
        search.visible = btn.active;
        const n_sel = panel.active.length;
        const arrow = btn.active ? '▲' : '▼';
        btn.label = 'Locations ' + arrow + '  (' + n_sel + ' selected)';
        """,
    ))

    # Search: auto-add all matches to the pinned selection, then rebuild.
    # Typing "san" → all "san..." locations jump to the top (checked) immediately.
    # Clearing the search → pinned locations stay selected; full unselected list shows below.
    loc_search.js_on_change("value", CustomJS(
        args=dict(chk_loc=chk_loc, loc_filter_src=loc_filter_src, selected_src=selected_src,
                  guard_src=guard_src, btn=loc_toggle, loc_search=loc_search,
                  all_labels=all_loc_labels),
        code="""
        const q_typed = cb_obj.value.trim().toLowerCase();
        if (q_typed !== "") {
            // Auto-add every matching location to the pinned selection
            const cur_sel = new Set(selected_src.data.orig_idx);
            const new_sel = selected_src.data.orig_idx.slice();
            for (let i = 0; i < all_labels.length; i++) {
                if (!cur_sel.has(i) && all_labels[i].toLowerCase().includes(q_typed)) {
                    new_sel.push(i);
                }
            }
            selected_src.data = {"orig_idx": new_sel};
        }
        // Rebuild: pinned items at top, remaining unselected filtered below
        // (_JS_REBUILD declares its own const q_val — do NOT declare q_val above)
        """ + _JS_REBUILD,
    ))

    # Check/uncheck: update selected_src, then rebuild so pinned section stays correct
    chk_loc.js_on_change("active", CustomJS(
        args=dict(chk_loc=chk_loc, loc_filter_src=loc_filter_src, selected_src=selected_src,
                  guard_src=guard_src, btn=loc_toggle, loc_search=loc_search,
                  all_labels=all_loc_labels),
        code="""
        if (guard_src.data.busy[0]) return;

        // Determine new set of selected original indices from current active list.
        // Display layout: [pinned selected (0..n_old_sel-1)] [unselected matches (n_old_sel..)]
        const orig_map   = loc_filter_src.data.orig_idx;
        const n_old_sel  = selected_src.data.orig_idx.length;
        const active_set = new Set(cb_obj.active);
        const new_sel    = [];

        for (let i = 0; i < n_old_sel; i++) {          // previously pinned — keep if still checked
            if (active_set.has(i)) new_sel.push(selected_src.data.orig_idx[i]);
        }
        for (let i = n_old_sel; i < cb_obj.labels.length; i++) {  // unselected — add if newly checked
            if (active_set.has(i)) new_sel.push(orig_map[i]);
        }

        selected_src.data = {"orig_idx": new_sel};
        """ + _JS_REBUILD,
    ))

    # -- CustomJS callback --
    Q_LABELS_JS = {v: lbl for v, lbl in q_opts}

    # Local unit selector for the bar chart section (stays in sync with the line plot one)
    unit_sel_bar = Select(title="Units:", value="mm",
                          options=[("mm", "mm"), ("cm", "cm"), ("m", "m")], width=100)

    JS_BAR = """
    const wf    = wf_sel.value;
    const comp  = comp_sel.value;
    const scale = scale_sel.value;
    const year  = parseInt(year_sel.value);
    const q_key = q_sel.value;
    const uf_map = {"mm": 1.0, "cm": 0.1, "m": 0.001};
    const uf = uf_map[unit_sel.value] || 1.0;

    // Active SSPs from checkbox
    const active_ssp_set = new Set(chk_ssp.active);
    const active_ssps    = plot_ssps.filter((_, i) => active_ssp_set.has(i));
    const n_active_ssps  = active_ssps.length;

    // Active locations from CheckboxGroup.
    // chk_loc shows only the filtered subset — loc_filter_src maps filtered index → original index.
    const filter_orig     = loc_filter_src.data.orig_idx;
    const active_filtered = Array.from(chk_loc.active);
    const n_active_locs   = active_filtered.length;

    if (n_active_ssps === 0 || n_active_locs === 0) {
        source_bar.data = {
            x: [], y: [], colors: [], ssp_labels: [],
            loc_names: [], loc_ids: [], loc_lat: [], loc_lon: [],
        };
        source_bar.change.emit();
        return;
    }

    // Bar widths scale with active SSP count; group centers stay at integer positions.
    const new_bar_w      = Math.min(0.15, 0.8 / n_active_ssps);
    const new_half_group = (n_active_ssps * new_bar_w) / 2.0;

    const xs = [], ys = [], colors = [], ssp_labels = [];
    const loc_names_out = [], loc_ids_out = [], loc_lat_out = [], loc_lon_out = [];

    for (let li2 = 0; li2 < n_active_locs; li2++) {
        const fi     = active_filtered[li2];           // index in filtered CheckboxGroup
        const li     = filter_orig[fi];                // original index in full loc arrays
        const loc_id = (scale === "global") ? -1 : loc_ids_arr[li];
        for (let si = 0; si < n_active_ssps; si++) {
            const ssp = active_ssps[si];
            const x   = li2 + si * new_bar_w - new_half_group + new_bar_w / 2.0;
            const key = ssp + "|" + comp + "|" + wf + "|" + scale + "|" + loc_id;
            const d   = window.FACTS_DATA[key];
            let   val = 0.0;
            if (d) {
                const idx = d.years.indexOf(year);
                if (idx !== -1 && d[q_key] !== undefined) val = d[q_key][idx];
            }
            xs.push(x);
            ys.push(val * uf);
            colors.push(ssp_color_map[ssp]);
            ssp_labels.push(ssp_label_map[ssp] || ssp);
            loc_names_out.push(loc_names_arr[li]);
            loc_ids_out.push(String(loc_ids_arr[li]));
            loc_lat_out.push(loc_lat_arr[li]);
            loc_lon_out.push(loc_lon_arr[li]);
        }
    }

    source_bar.data = {
        x: xs, y: ys, colors: colors, ssp_labels: ssp_labels,
        loc_names: loc_names_out, loc_ids: loc_ids_out,
        loc_lat: loc_lat_out, loc_lon: loc_lon_out,
    };
    source_bar.change.emit();

    // Update x-axis labels via label_cds — the FuncTickFormatter reads from this CDS
    // reactively, so labels always match the current selection (unlike major_label_overrides).
    const new_ticks = [];
    const new_names = [];
    for (let li2 = 0; li2 < n_active_locs; li2++) {
        const li = filter_orig[active_filtered[li2]];
        new_ticks.push(li2);
        new_names.push(loc_names_arr[li]);
    }
    x_ticker.ticks = new_ticks;
    label_cds.data = {pos: new_ticks, name: new_names};
    label_cds.change.emit();
    p_bar.x_range.start = -0.6;
    p_bar.x_range.end   = Math.max(0.4, n_active_locs - 0.4);

    const q_label = q_label_map[q_key] || q_key;
    p_bar.title.text = "RSL Projections at " + year +
        " — SSP Comparison per Tide Gauge" +
        "  (" + wf + ", " + comp + ", " + scale + ", " + q_label + ", " + unit_sel.value + ")";
    y_axis_bar.axis_label = "RSL Change (" + unit_sel.value + ")";
    """

    cb = CustomJS(
        args=dict(
            source_bar    = source_bar,
            p_bar         = p_bar,
            label_cds     = label_cds,
            wf_sel        = wf_sel,
            comp_sel      = comp_sel,
            scale_sel     = scale_sel,
            year_sel      = year_sel,
            q_sel         = q_sel,
            chk_ssp       = chk_ssp,
            chk_loc       = chk_loc,
            loc_filter_src= loc_filter_src,
            x_ticker      = x_ticker,
            plot_ssps     = plot_ssps,
            loc_ids_arr   = loc_ids,
            loc_names_arr = loc_names,
            loc_lat_arr   = loc_lat,
            loc_lon_arr   = loc_lon,
            n_locs        = n_locs,
            ssp_color_map = {s: SSP_COLORS.get(s, _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
                             for i, s in enumerate(plot_ssps)},
            ssp_label_map = {s: SSP_LABELS.get(s, s) for s in plot_ssps},
            q_label_map   = Q_LABELS_JS,
            unit_sel      = unit_sel,
            y_axis_bar    = p_bar.yaxis[0],
        ),
        code=JS_BAR,
    )
    wf_sel.js_on_change("value",       cb)
    comp_sel.js_on_change("value",     cb)
    scale_sel.js_on_change("value",    cb)
    year_sel.js_on_change("value",     cb)
    q_sel.js_on_change("value",        cb)
    chk_ssp.js_on_change("active",     cb)
    chk_loc.js_on_change("active",     cb)
    unit_sel.js_on_change("value",     cb)   # driven by the shared line-plot widget

    # -- Y-axis range slider (same pattern as line plot section) --
    bar_ys = [v for v in init_data["y"] if v is not None]
    bar_ymin = float(min(bar_ys)) if bar_ys else YMIN_FIXED
    bar_ymax = float(max(bar_ys)) if bar_ys else YMAX_FIXED
    bar_pad  = max(50.0, 0.05 * (bar_ymax - bar_ymin))
    bar_y_init_min = max(YMIN_FIXED, bar_ymin - bar_pad)
    bar_y_init_max = min(YMAX_FIXED, bar_ymax + bar_pad)
    bar_y_step = max(1.0, round((bar_y_init_max - bar_y_init_min) / 100, 1))

    p_bar.y_range = Range1d(bar_y_init_min, bar_y_init_max)

    y_bar_slider = RangeSlider(
        title="Y range",
        start=YMIN_FIXED, end=YMAX_FIXED,
        value=(bar_y_init_min, bar_y_init_max),
        step=bar_y_step, width=600,
    )
    y_bar_slider.js_on_change("value", CustomJS(
        args=dict(p=p_bar, s=y_bar_slider),
        code="""
        p.y_range.start = Math.max(s.start, s.value[0]);
        p.y_range.end   = Math.min(s.end,   s.value[1]);
        """,
    ))
    # Bar axis label + slider reset — driven by the shared unit_sel widget
    unit_sel.js_on_change("value", CustomJS(
        args=dict(p=p_bar, y_bar_slider=y_bar_slider, unit_sel=unit_sel,
                  y_axis_bar=p_bar.yaxis[0]),
        code="""
        const uf_map = {"mm": 1.0, "cm": 0.1, "m": 0.001};
        const uf = uf_map[unit_sel.value] || 1.0;
        const ymin_u = -500 * uf;
        const ymax_u = 4000 * uf;
        y_bar_slider.start      = ymin_u;
        y_bar_slider.end        = ymax_u;
        y_bar_slider.value      = [ymin_u, ymax_u];
        p.y_range.start         = ymin_u;
        p.y_range.end           = ymax_u;
        y_axis_bar.axis_label   = "RSL Change (" + unit_sel.value + ")";
        """,
    ))

    # ── unit_sel_bar is a display-only mirror — syncs both ways with unit_sel ──
    # Bar → shared: user changes bar dropdown → update shared widget → all callbacks fire
    unit_sel_bar.js_on_change("value", CustomJS(
        args=dict(other=unit_sel),
        code="if (other.value !== cb_obj.value) other.value = cb_obj.value;",
    ))
    # Shared → bar: shared widget changes (e.g. from line plot) → update bar display
    unit_sel.js_on_change("value", CustomJS(
        args=dict(other=unit_sel_bar),
        code="if (other.value !== cb_obj.value) other.value = cb_obj.value;",
    ))

    ssp_chk_label = Div(
        text="<b style='font-size:12px;'>Scenarios:</b>",
        width=130,
        styles={"padding-top": "6px"},
    )

    bar_head = Div(text="""
<div style="margin-top:32px;margin-bottom:6px;">
  <u>FACTS <b>sea-level projections — scenario comparison</b></u> (GROUPED BAR CHART)<br>
  Each group = one tide gauge location. Bars within each group = selected scenarios.<br>
  Select <b>workflow</b>, <b>component</b>, <b>scale</b>, <b>year</b>, <b>quantile</b>,
  <b>scenarios</b>, and <b>locations</b>. Tick any combination of locations to compare them.
  Hover over any bar for location details and RSL value (mm).
</div>
""", width=1200)

    return column(
        bar_head,
        row(wf_sel, comp_sel, scale_sel, year_sel, q_sel, unit_sel_bar),
        row(ssp_chk_label, chk_ssp),
        row(column(loc_toggle, loc_search, chk_loc)),
        y_bar_slider,
        p_bar,
    )


# ─────────────────────────────────────────────────────────
# Dashboard builder
# ─────────────────────────────────────────────────────────

def build_dashboard(
    data_dict:     dict,
    years:         list,
    locations:     list,
    location_meta: dict,
    ssps:          list,
    wfs:           list,
    output_path:   Path,
    title:         str = "FACTS Sea-Level Projections",
    single_nc_mode: bool = False,
):
    """
    Build and save the Bokeh interactive dashboard HTML.

    Args:
        data_dict:      Keyed by "{ssp}|{component}|{wf}|{scale}|{loc_id}".
        years:          Reference year list for axis range.
        locations:      List of dicts from location.lst (name, id, lat, lon).
        location_meta:  Dict of {int loc_id: {lat, lon}}.
        ssps:           List of SSP tag strings.
        wfs:            List of workflow ID strings.
        output_path:    Path to write the output HTML file.
        title:          Dashboard title string.
        single_nc_mode: When True, adapts the layout for a single-NC-file load:
                        cycles slots through different locations, disables dead
                        dropdowns, adds a metadata banner, and hides the
                        component table (which would be a 1×1 grid).

    Example:
        build_dashboard(data_dict, years, locations, location_meta,
                        ssps, wfs, Path("dashboard.html"))
    """
    def ssp_color(ssp: str, idx: int) -> str:
        return SSP_COLORS.get(ssp, _FALLBACK_COLORS[idx % len(_FALLBACK_COLORS)])

    # ── Location option lists ──────────────────────────────
    loc_id_to_name = {int(loc["id"]): loc["name"] for loc in locations}
    location_meta_js = {}
    for loc_id, meta in location_meta.items():
        name = loc_id_to_name.get(loc_id, ("Global" if loc_id == -1 else f"Loc {loc_id}"))
        location_meta_js[str(loc_id)] = {
            "name": name,
            "lat":  meta["lat"],
            "lon":  meta["lon"],
        }
    loc_order  = [-1] + [int(loc["id"]) for loc in locations]
    all_loc_ids = sorted(
        [int(k) for k in location_meta_js],
        key=lambda x: loc_order.index(x) if x in loc_order else 999,
    )
    loc_options_all = []
    for lid in all_loc_ids:
        info  = location_meta_js[str(lid)]
        name  = info["name"]
        label = (
            f"{name}  (global)"
            if lid == -1
            else f"{name}  ({info['lat']:.2f}°N, {info['lon']:.2f}°E)"
            if info["lat"] is not None
            else name
        )
        loc_options_all.append((str(lid), label))

    # ── Default slot configs ────────────────────────────────
    # In single-NC mode there is only 1 SSP/workflow/component — cycle locations
    # so the 6 slots show 6 different stations instead of 6 identical lines.
    # In multi-file mode cycle SSPs as before.
    first_loc = str(all_loc_ids[1]) if len(all_loc_ids) > 1 else str(all_loc_ids[0])
    # Collect non-global loc IDs in order for single-NC location cycling
    local_loc_ids = [lid for lid in all_loc_ids if lid != -1]

    slot_defaults = []
    for i in range(6):
        if single_nc_mode:
            # Cycle through different locations; SSP/wf/comp fixed to the one available
            cycle_lid = local_loc_ids[i % len(local_loc_ids)] if local_loc_ids else all_loc_ids[0]
            loc_d   = str(cycle_lid)
            ssp_d   = ssps[0]
            wf_d    = wfs[0]
            comp_d  = COMPONENTS[0]
            scale_d = "local"
        else:
            ssp_d   = ssps[i % len(ssps)]
            wf_d    = wfs[0]
            comp_d  = "total"
            scale_d = "local"
            loc_d   = first_loc

        key = f"{ssp_d}|{comp_d}|{wf_d}|{scale_d}|{loc_d}"
        if key not in data_dict:
            key = next((k for k in data_dict if k.startswith(f"{ssp_d}|")), next(iter(data_dict)))
            parts = key.split("|")
            ssp_d, comp_d, wf_d, scale_d, loc_d = parts[0], parts[1], parts[2], parts[3], parts[4]
        slot_defaults.append({"ssp": ssp_d, "comp": comp_d, "wf": wf_d,
                               "scale": scale_d, "loc": loc_d, "key": key})

    # ── ColumnDataSources ──────────────────────────────────
    def empty_data(n):
        return dict(years=years[:n] if years else [], med=[0.0]*n, lo=[0.0]*n, hi=[0.0]*n)

    sources = []
    for sd in slot_defaults:
        d = data_dict.get(sd["key"], empty_data(len(years)))
        n = len(d.get("years", []))
        loc_info_sd = location_meta_js.get(sd["loc"], {})
        loc_nm_sd   = loc_info_sd.get("name", sd["loc"])
        ssp_lbl_sd  = SSP_LABELS.get(sd["ssp"], sd["ssp"])
        sources.append(ColumnDataSource(data=dict(
            years=d["years"], med=d["med"], lo=d["lo"], hi=d["hi"],
            loc_name=[loc_nm_sd]   * n,
            ssp_label=[ssp_lbl_sd] * n,
            wf_label=[sd["wf"]]    * n,
        )))

    # ── Y range from data ──────────────────────────────────
    # Initial view is scaled to the 6 default slots so the lines are visible on first load.
    # The slider end extends to the global data max so users can explore other workflows.
    slot_hi = [v for sd in slot_defaults
               for v in data_dict.get(sd["key"], {}).get("hi", []) if v is not None]
    all_hi  = [v for d in data_dict.values() for v in d["hi"] if v is not None]
    ymax_slot   = float(max(slot_hi)) if slot_hi else YMAX_FIXED
    ymax_data   = float(max(all_hi))  if all_hi  else YMAX_FIXED
    y_pad       = 0.05 * ymax_slot
    # y_init_min fixed at 0 so screenshots are comparable across SSPs/datasets
    y_init_min  = 0.0
    y_init_max  = ymax_slot + y_pad
    y_slider_end = YMAX_FIXED
    x_init_min  = float(min(years)) if years else XMIN_FIXED
    x_init_max  = float(max(years)) if years else XMAX_FIXED

    # ── Figure ─────────────────────────────────────────────
    p = figure(
        width=900, height=500,
        title="Interactive sea-level projections",
        x_axis_label="Years",
        y_axis_label="Sea-level change (mm)",
        x_range=Range1d(x_init_min, x_init_max),
        y_range=Range1d(y_init_min, y_init_max),
        toolbar_location="above",
    )
    p.toolbar.autohide = False

    slot_renderers = []
    colors = []
    for i, sd in enumerate(slot_defaults):
        color = ssp_color(sd["ssp"], i)
        colors.append(color)
        src   = sources[i]
        style = COMPONENT_STYLES.get(sd["comp"], "solid")

        # Each plot slot pre-creates all 7 renderer types (1 band + 7 line/marker styles).
        # Only one renderer is made visible at a time based on the selected component.
        # This approach avoids dynamic glyph creation in the browser — Bokeh's CustomJS
        # cannot add new renderers after page load, so we create all upfront and toggle visibility.
        band       = p.varea(x="years", y1="lo", y2="hi", source=src,
                             fill_color=color, fill_alpha=0.2)
        r_solid    = p.line("years", "med", source=src, line_width=2,
                            line_color=color, line_dash=[])
        r_dashed   = p.line("years", "med", source=src, line_width=2,
                            line_color=color, line_dash="dashed")
        r_dotted   = p.line("years", "med", source=src, line_width=2,
                            line_color=color, line_dash="dotted")
        r_circle   = p.scatter("years", "med", source=src, marker="circle",   size=7,
                               line_color=color, fill_color=None)
        r_diamond  = p.scatter("years", "med", source=src, marker="diamond",  size=9,
                               line_color=color, fill_color=None)
        r_asterisk = p.scatter("years", "med", source=src, marker="asterisk", size=10,
                               line_color=color, fill_color=None)
        r_triangle = p.scatter("years", "med", source=src, marker="triangle", size=9,
                               line_color=color, fill_color=None)

        # Set initial visibility — only the renderer matching the default component is shown
        r_solid.visible    = (style == "solid")
        r_dashed.visible   = (style == "dashed")
        r_dotted.visible   = (style == "dotted")
        r_circle.visible   = (style == "circle")
        r_diamond.visible  = (style == "diamond")
        r_asterisk.visible = (style == "asterisk")
        r_triangle.visible = (style == "triangle")

        slot_renderers.append({
            "band": band, "solid": r_solid, "dashed": r_dashed, "dotted": r_dotted,
            "circle": r_circle, "diamond": r_diamond,
            "asterisk": r_asterisk, "triangle": r_triangle,
        })

        # Per-slot HoverTool scoped only to this slot's line/scatter renderers.
        # Scoping prevents cross-slot overlap — hovering one line shows only that line's data.
        p.add_tools(HoverTool(
            renderers=[r_solid, r_dashed, r_dotted, r_circle, r_diamond, r_asterisk, r_triangle],
            tooltips=[
                ("Location", "@loc_name"),
                ("SSP",      "@ssp_label"),
                ("Workflow", "@wf_label"),
                ("Year",     "@years{0}"),
                ("Median",   "@med{0.0} mm"),
                ("Range",    "@lo{0.0} – @hi{0.0} mm"),
            ],
        ))

    # ── Per-slot widgets ───────────────────────────────────
    wf_opts    = [(wf, wf) for wf in wfs]
    ssp_opts   = [(ssp, SSP_LABELS.get(ssp, ssp)) for ssp in ssps]
    comp_opts  = [(c, COMPONENT_LABELS.get(c, c)) for c in COMPONENTS]
    scale_opts = [("local", "Local RSL"), ("global", "Global Mean SL")]

    style_preview_map_js = {
        k: f'<span style="font-family:monospace;font-size:14px;">{v}</span>'
        for k, v in _STYLE_PREVIEW.items()
    }

    slot_widgets = []
    for i, sd in enumerate(slot_defaults):
        color    = ssp_color(sd["ssp"], i)
        style    = COMPONENT_STYLES.get(sd["comp"], "solid")
        loc_info = location_meta_js.get(sd["loc"], {})
        loc_name = loc_info.get("name", sd["loc"])
        lat_v    = loc_info.get("lat")
        lon_v    = loc_info.get("lon")

        n = i + 1
        # In single-NC mode, dropdowns with only 1 option are disabled so the user
        # doesn't waste time trying to switch something that has no alternatives.
        _dis_wf   = single_nc_mode and len(wf_opts)   == 1
        _dis_ssp  = single_nc_mode and len(ssp_opts)  == 1
        _dis_comp = single_nc_mode and len(comp_opts) == 1
        wf_sel   = Select(title="Workflow",   value=sd["wf"],    options=wf_opts,    width=170, disabled=_dis_wf)
        ssp_sel  = Select(title="Scenario",    value=sd["ssp"],   options=ssp_opts,   width=140, disabled=_dis_ssp)
        comp_sel = Select(title="Component",  value=sd["comp"],  options=comp_opts,  width=200, disabled=_dis_comp)
        scale_sel= Select(title="Scale",      value=sd["scale"], options=scale_opts, width=140)
        loc_sel  = Select(title="Location", value=sd["loc"], options=loc_options_all, width=240)

        # Search bar: filters loc_sel.options in real-time. Hidden until toggle is clicked.
        loc_search_slot = TextInput(placeholder="Search...", width=240, visible=False)
        loc_search_slot.js_on_change("value", CustomJS(
            args=dict(loc_sel=loc_sel, all_opts=loc_options_all),
            code="""
            const q = cb_obj.value.trim().toLowerCase();
            const new_opts = q === ""
                ? all_opts.slice()
                : all_opts.filter(([v, l]) => l.toLowerCase().includes(q));
            if (new_opts.length > 0) {
                loc_sel.options = new_opts;
                if (!new_opts.some(([v]) => v === loc_sel.value)) {
                    loc_sel.value = new_opts[0][0];
                }
            }
            """,
        ))

        # Toggle shows/hides the search bar. loc_sel always stays visible (Bokeh Select
        # does not reliably re-flow when toggled from visible=False to True in a column layout).
        _init_loc_lbl = next((lbl for v, lbl in loc_options_all if v == sd["loc"]), sd["loc"])
        loc_toggle_slot = Toggle(
            label=f"Search ▼  location",
            active=False,
            button_type="light",
            width=240,
        )
        loc_toggle_slot.js_on_change("active", CustomJS(
            args=dict(search_box=loc_search_slot, btn=loc_toggle_slot),
            code="""
            search_box.visible = btn.active;
            btn.label = btn.active ? 'Search ▲  location' : 'Search ▼  location';
            """,
        ))

        color_box    = Div(text=_color_box_html(color),  width=30,  height=50)
        style_box    = Div(text=_style_box_html(style),  width=80,  height=50)
        loc_info_div = Div(
            text=_loc_info_html(int(sd["loc"]), loc_name, lat_v, lon_v),
            width=180, height=60,
        )
        chk = Checkbox(label="Show", active=True)
        row_label = Div(
            text=f'<div style="font-weight:bold;font-size:12px;color:#555;margin-top:22px;">Line {n}</div>',
            width=45, height=50,
        )

        slot_widgets.append({
            "wf": wf_sel, "ssp": ssp_sel, "comp": comp_sel,
            "scale": scale_sel, "loc": loc_sel,
            "loc_toggle": loc_toggle_slot, "loc_search": loc_search_slot,
            "color_box": color_box, "style_box": style_box,
            "loc_info": loc_info_div, "chk": chk, "row_label": row_label,
        })

    # ── Global quantile selector for line plot ─────────────
    q_line_opts = [
        ("narrow", "17th–83rd percentile"),
        ("wide",   "5th–95th percentile"),
    ]
    q_line_sel = Select(title="Shading:", value="narrow", options=q_line_opts, width=200)

    # ── Global unit selector (mm / cm / m) ─────────────────
    unit_sel = Select(title="Units:", value="mm",
                      options=[("mm", "mm"), ("cm", "cm"), ("m", "m")], width=100)

    # ── CustomJS callbacks ─────────────────────────────────
    # JS_UPDATE fires when any selector (workflow, SSP, component, scale, location) changes.
    # Key format must match Python's _store_result: "{ssp}|{comp}|{wf}|{scale}|{loc_id}"
    # loc.value is "-1" for Global Mean SL; a positive integer string for a tide gauge.
    JS_UPDATE = """
    const key = ssp.value + "|" + comp.value + "|" + wf.value + "|" + scale.value + "|" + loc.value;
    const d   = window.FACTS_DATA[key];

    if (!d) {
        console.warn("No data for key:", key);
        // Clear the ColumnDataSource so stale data from a previous selection is not shown.
        // (e.g. VLM has no global variant — switching to global must blank the plot, not leave
        //  the previous local VLM curve visible)
        source.data = { years: [], med: [], lo: [], hi: [], loc_name: [], ssp_label: [], wf_label: [] };
        source.change.emit();
        band.visible = r_solid.visible = r_dashed.visible = r_dotted.visible =
        r_circle.visible = r_diamond.visible = r_asterisk.visible = r_triangle.visible = false;
    } else {
        const wide = q_line_sel.value === 'wide';
        const uf_map = {"mm": 1.0, "cm": 0.1, "m": 0.001};
        const uf = uf_map[unit_sel.value] || 1.0;
        const lo_arr = (wide && d.vlo) ? d.vlo : d.lo;
        const hi_arr = (wide && d.vhi) ? d.vhi : d.hi;
        const _n      = d.years.length;
        const _loc_nm = (location_meta[loc.value] || {}).name || loc.value;
        const _ssp_lb = ssp_labels[ssp.value] || ssp.value;
        source.data = {
            years:     d.years,
            med:       d.med.map(v => v * uf),
            lo:        lo_arr.map(v => v * uf),
            hi:        hi_arr.map(v => v * uf),
            loc_name:  Array(_n).fill(_loc_nm),
            ssp_label: Array(_n).fill(_ssp_lb),
            wf_label:  Array(_n).fill(wf.value),
        };
        source.change.emit();

        // Restore band visibility — may have been hidden by a previous no-data selection
        band.visible = chk.active;

        // Colour: SSP_COLORS for known SSPs, fixed slot color for everything else
        const c = ssp_colors[ssp.value] || slot_color;
        band.glyph.fill_color       = c;
        r_solid.glyph.line_color    = c;
        r_dashed.glyph.line_color   = c;
        r_dotted.glyph.line_color   = c;
        r_circle.glyph.line_color   = c;
        r_diamond.glyph.line_color  = c;
        r_asterisk.glyph.line_color = c;
        r_triangle.glyph.line_color = c;
        band.change.emit();

        // Color box
        color_box.text = `<div style="display:inline-block;width:18px;height:18px;
            background-color:${c};border:1px solid #444;border-radius:3px;
            margin-top:6px;"></div>`;

        // Style from component
        const style = comp_styles[comp.value] || "solid";
        r_solid.visible = r_dashed.visible = r_dotted.visible = r_circle.visible =
        r_diamond.visible = r_asterisk.visible = r_triangle.visible = false;
        if      (style === "solid")    r_solid.visible    = true;
        else if (style === "dashed")   r_dashed.visible   = true;
        else if (style === "dotted")   r_dotted.visible   = true;
        else if (style === "circle")   r_circle.visible   = true;
        else if (style === "diamond")  r_diamond.visible  = true;
        else if (style === "asterisk") r_asterisk.visible = true;
        else if (style === "triangle") r_triangle.visible = true;
        else                           r_solid.visible    = true;

        if (!chk.active) {
            band.visible = r_solid.visible = r_dashed.visible = r_dotted.visible =
            r_circle.visible = r_diamond.visible = r_asterisk.visible = r_triangle.visible = false;
        }

        style_box.text = style_preview_map[style] || style_preview_map["solid"];
    }

    // Always update location info regardless of data availability
    const li = location_meta[loc.value];
    if (li) {
        const lat_txt = (li.lat === null || li.lat === undefined || !isFinite(li.lat)) ? "NA" : li.lat.toFixed(3);
        const lon_txt = (li.lon === null || li.lon === undefined || !isFinite(li.lon)) ? "NA" : li.lon.toFixed(3);
        loc_info.text = `<div style="font-size:11px;line-height:1.5;">
            <b>Location ${loc.value}</b><br>
            <b>${li.name}</b><br>
            lat: ${lat_txt} &nbsp; lon: ${lon_txt}</div>`;
    }
    """

    # JS_VISIBILITY fires only when the checkbox (show/hide line) is toggled.
    # Kept separate from JS_UPDATE so toggling visibility doesn't re-read or re-emit data.
    JS_VISIBILITY = """
    const show  = chk.active;
    const style = comp_styles[comp.value] || "solid";
    band.visible = show;
    // Reset all line renderers, then re-enable only the one matching current component style
    r_solid.visible = r_dashed.visible = r_dotted.visible = r_circle.visible =
    r_diamond.visible = r_asterisk.visible = r_triangle.visible = false;
    if (show) {
        if      (style === "solid")    r_solid.visible    = true;
        else if (style === "dashed")   r_dashed.visible   = true;
        else if (style === "dotted")   r_dotted.visible   = true;
        else if (style === "circle")   r_circle.visible   = true;
        else if (style === "diamond")  r_diamond.visible  = true;
        else if (style === "asterisk") r_asterisk.visible = true;
        else if (style === "triangle") r_triangle.visible = true;
        else                           r_solid.visible    = true;
    }
    """

    for i, (sw, sr) in enumerate(zip(slot_widgets, slot_renderers)):
        common = dict(
            source=sources[i],
            wf=sw["wf"], ssp=sw["ssp"], comp=sw["comp"],
            scale=sw["scale"], loc=sw["loc"],
            chk=sw["chk"],
            band=sr["band"], r_solid=sr["solid"], r_dashed=sr["dashed"],
            r_dotted=sr["dotted"], r_circle=sr["circle"], r_diamond=sr["diamond"],
            r_asterisk=sr["asterisk"], r_triangle=sr["triangle"],
            ssp_colors={s: SSP_COLORS[s] for s in ssps if s in SSP_COLORS},
            ssp_labels={s: SSP_LABELS.get(s, s) for s in ssps},
            slot_color=colors[i],
            comp_styles=COMPONENT_STYLES,
            color_box=sw["color_box"],
            style_box=sw["style_box"],
            style_preview_map=style_preview_map_js,
            loc_info=sw["loc_info"],
            location_meta=location_meta_js,
            q_line_sel=q_line_sel,
            unit_sel=unit_sel,
        )
        cb_update = CustomJS(args=common, code=JS_UPDATE)
        cb_vis    = CustomJS(args=common, code=JS_VISIBILITY)

        for sel in (sw["wf"], sw["ssp"], sw["comp"], sw["scale"], sw["loc"]):
            sel.js_on_change("value", cb_update)
        q_line_sel.js_on_change("value", cb_update)
        unit_sel.js_on_change("value", cb_update)
        sw["chk"].js_on_change("active", cb_vis)

    # ── X / Y range sliders ────────────────────────────────
    y_step   = max(1.0, round((y_init_max - y_init_min) / 100, 1))
    x_slider = RangeSlider(
        title="X range (years)",
        start=XMIN_FIXED, end=XMAX_FIXED,
        value=(x_init_min, x_init_max),
        step=1, width=600,
    )
    y_slider = RangeSlider(
        title="Y range",
        start=YMIN_FIXED, end=y_slider_end,
        value=(y_init_min, y_init_max),
        step=y_step, width=600,
    )
    x_slider.js_on_change("value", CustomJS(args=dict(p=p, s=x_slider), code="""
        p.x_range.start = Math.max(s.start, s.value[0]);
        p.x_range.end   = Math.min(s.end,   s.value[1]);
    """))
    y_slider.js_on_change("value", CustomJS(args=dict(p=p, s=y_slider), code="""
        p.y_range.start = Math.max(s.start, s.value[0]);
        p.y_range.end   = Math.min(s.end,   s.value[1]);
    """))
    unit_sel.js_on_change("value", CustomJS(
        args=dict(p=p, y_slider=y_slider, unit_sel=unit_sel, y_axis=p.yaxis[0]),
        code="""
        const uf_map = {"mm": 1.0, "cm": 0.1, "m": 0.001};
        const uf = uf_map[unit_sel.value] || 1.0;
        const ymin_u = -500 * uf;
        const ymax_u = 4000 * uf;
        y_slider.start   = ymin_u;
        y_slider.end     = ymax_u;
        y_slider.value   = [ymin_u, ymax_u];
        p.y_range.start  = ymin_u;
        p.y_range.end    = ymax_u;
        y_axis.axis_label = "Sea-level change (" + unit_sel.value + ")";
        """,
    ))

    # ── Layout rows ────────────────────────────────────────
    # loc_search sits above loc_sel in a compact column — lets users type to filter
    # 1000+ locations without scrolling through a raw dropdown.
    ctrl_rows = []
    for sw in slot_widgets:
        ctrl_rows.append(row(
            sw["row_label"],
            sw["wf"], sw["ssp"], sw["color_box"],
            sw["comp"], sw["style_box"],
            sw["scale"],
            column(sw["loc_toggle"], sw["loc_search"], sw["loc"]), sw["loc_info"], sw["chk"],
        ))
    controls_block = column(*ctrl_rows, row(q_line_sel, unit_sel), x_slider, y_slider)

    # ── Header ─────────────────────────────────────────────
    desc_head = Div(text=f"""
<div style="margin-bottom:8px;">
<br>
  <b>{title}</b><br><br>
  Select a <b>workflow</b>, <b>Scenario</b> and <b>Component</b> to view
  <u>median</u> (p50) and <u>17th&#8211;83rd percentile</u> (shading).<br>
  For a description of <b>Workflows</b>, see the table below.
</div>
""", width=900)

    # ── Legend ─────────────────────────────────────────────
    _ssp_color_entries = " &nbsp;\n    ".join(
        f'<span style="color:{SSP_COLORS.get(s, _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])}">&#9632;</span> {SSP_LABELS.get(s, s)}'
        for i, s in enumerate(ssps)
    )
    legend_html = f"""
<div style="margin-top:8px;line-height:2.0;font-size:13px;">
  <div>
    <b>Component legend:</b> &nbsp;
    <span style="font-family:monospace;">— — —</span> &nbsp;total &nbsp;&nbsp;
    <span style="font-family:monospace;">────</span> &nbsp;AIS &nbsp;&nbsp;
    <span style="font-family:monospace;">⋅ ⋅ ⋅ ⋅</span> &nbsp;GrIS &nbsp;&nbsp;
    ○ &nbsp;Glaciers &nbsp;&nbsp;
    ◇ &nbsp;Sterodynamics &nbsp;&nbsp;
    * &nbsp;Land water storage &nbsp;&nbsp;
    ▲ &nbsp;VLM
  </div>
  <div>
    <b>Scenario colours:</b> &nbsp;
    {_ssp_color_entries}
  </div>
</div>
"""
    text_legend = Div(text=legend_html, width=900)

    # ── Citation + workflow table ───────────────────────────
    citation = Div(text=f"""
<div style="margin-bottom:8px;">
<br>
  Generated by <code>facts_dashboard.py</code>.
  Values shown in the selected unit (mm by default) relative to the experiment base year. Shading = p17&#8211;p83.
  {_workflow_table_html()}
</div>
""", width=900)

    # ── Single-NC metadata banner ──────────────────────────
    if single_nc_mode:
        ssp_label  = SSP_LABELS.get(ssps[0], ssps[0])
        comp_label = COMPONENT_LABELS.get(COMPONENTS[0], COMPONENTS[0])
        wf_label   = WF_LABELS.get(wfs[0], wfs[0])
        yr_start   = years[0] if years else "?"
        yr_end     = years[-1] if years else "?"
        n_locs     = len([lid for lid in all_loc_ids if lid != -1])
        single_nc_banner = Div(text=f"""
<div style="background:#f0f4fa;border:1px solid #c5d3e8;border-radius:5px;
            padding:10px 14px;margin-bottom:10px;font-size:13px;font-family:Arial,sans-serif;">
  <b>Single-file mode</b> &mdash; auto-detected from filename:<br>
  &nbsp;&nbsp;<b>Scenario:</b> {ssp_label} &nbsp;|&nbsp;
  <b>Component:</b> {comp_label} &nbsp;|&nbsp;
  <b>Workflow:</b> {wf_label}<br>
  &nbsp;&nbsp;<b>Year range:</b> {yr_start}&ndash;{yr_end} &nbsp;|&nbsp;
  <b>Locations:</b> {n_locs} tide gauge stations<br>
  <span style="color:#666;font-size:11px;">
    Workflow, Scenario, and Component selectors are fixed to the values above.
    Use the Location selector in each line slot to compare different stations.
  </span>
</div>
""", width=950)
    else:
        single_nc_banner = None

    # ── STACKED BAR section ────────────────────────────────
    stacked_bar_section = _build_stacked_bar_section(
        data_dict, years, ssps, wfs, loc_options_all, location_meta_js, unit_sel,
    )

    # ── TABLE section — hidden in single-NC mode (1×1 grid adds no value) ──
    if not single_nc_mode:
        comp_table_section = _build_component_table_section(
            data_dict, years, ssps, wfs, loc_options_all, location_meta_js, unit_sel,
        )
    else:
        comp_table_section = None

    layout_items = [desc_head]
    if single_nc_banner:
        layout_items.append(single_nc_banner)
    layout_items += [controls_block, p, text_legend]
    if comp_table_section:
        layout_items.append(comp_table_section)
    layout_items.append(stacked_bar_section)
    layout_items.append(citation)

    dashboard = column(*layout_items)

    # Serialize data_dict ONCE as a global JS variable injected into the HTML.
    # Previously it was passed as a CustomJS arg to every callback (7 copies × ~30 MB).
    # Writing it as window.FACTS_DATA means Bokeh never serializes it at all —
    # all callbacks read window.FACTS_DATA directly, saving ~6/7 of the data payload.
    # Step 1: write valid Bokeh HTML via save() — data_dict is no longer in any CustomJS
    # args so Bokeh will NOT serialize it; the output is just the UI skeleton.
    save(dashboard, filename=str(output_path), resources=INLINE, title=title)

    # Step 2: post-process — inject data_dict ONCE as window.FACTS_DATA so all
    # callbacks can read it without 7x duplication.
    # Escape </ → <\/ so the browser HTML parser never treats a location name or data
    # value containing "</script>" as closing our script block.
    html = output_path.read_text(encoding="utf-8")
    data_json = json.dumps(data_dict).replace("</", "<\\/")
    data_script = "<script>\nwindow.FACTS_DATA = " + data_json + ";\n</script>\n"
    html = html.replace("</head>", data_script + "</head>", 1)
    output_path.write_text(html, encoding="utf-8")

    log.info("Dashboard saved → %s", output_path.resolve())
    log.info("Output size      : %.1f MB", output_path.stat().st_size / (1024 * 1024))

# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="facts_dashboard.py",
        description=(
            "Generate a self-contained interactive HTML dashboard "
            "from FACTS sea-level projection output (.nc files). "
            "6 independent line slots: workflow × SSP × component × scale × location."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python facts_dashboard.py --exp-root exp.alt.emis/
  python facts_dashboard.py --exp-root /data/facts/exp/ --output report.html
  python facts_dashboard.py --exp-root exp.alt.emis/ --title "Indian Ocean SSP runs"
        """,
    )
    parser.add_argument(
        "--exp-root", type=Path, default=None, metavar="DIR",
        help="Root directory containing coupling.ssp* experiment folders",
    )
    parser.add_argument(
        "--ssp-dir", type=str, action="append", default=[], metavar="DIR",
        dest="ssp_dirs",
        help=(
            "Path to a single SSP experiment folder (or its output/ subfolder). "
            "Repeat for each SSP: --ssp-dir /run1/coupling.ssp126/ --ssp-dir /run2/coupling.ssp585/"
        ),
    )
    parser.add_argument(
        "--single-nc-file", type=Path, default=None, metavar="FILE",
        help=(
            "Path to a single FACTS .nc file (sea_level_change variable). "
            "SSP, component, workflow, and scale are auto-detected from the filename. "
            "Produces the same full dashboard (line plot, bar chart, component table) "
            "from a single file rather than a full experiment tree."
        ),
    )
    parser.add_argument(
        "--confidence-root", type=Path, default=None, metavar="DIR",
        help=(
            "Root directory of AR6-style pre-computed confidence level files. "
            "Expected structure: DIR/{confidence_level}/{ssp}/{component}_{ssp}_{confidence_level}_values.nc. "
            "Use with --confidence-level to select low_confidence or medium_confidence."
        ),
    )
    parser.add_argument(
        "--confidence-level", default="medium_confidence",
        metavar="LEVEL",
        help=(
            "Confidence level sub-directory to load (default: medium_confidence). "
            "Options: medium_confidence, low_confidence, both. "
            "Use 'both' to load low and medium confidence together as separate workflow slots."
        ),
    )
    parser.add_argument(
        "--location-lst", type=Path, default=None, metavar="FILE",
        help=(
            "Path to a location.lst file (whitespace-separated name/id/lat/lon) used to "
            "resolve tide gauge names. Optional — if omitted the dashboard searches for "
            "location.lst automatically relative to the input data directory."
        ),
    )
    parser.add_argument("--output", type=Path, default=None, metavar="FILE",
                        help="Output HTML path (default: facts_dashboard.html next to exp-root)")
    parser.add_argument("--title", default=None,
                        help="Dashboard title shown in the header (auto-generated if omitted)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable DEBUG-level logging")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    # ── Single NC file mode ──────────────────────────────────
    if args.single_nc_file:
        nc_path = args.single_nc_file.resolve()
        if not nc_path.exists():
            log.error("--single-nc-file not found: %s", nc_path)
            sys.exit(1)

        default_out = nc_path.parent / "facts_dashboard.html"
        output_path = (args.output or default_out).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info("FACTS Dashboard Generator — single NC file mode")
        log.info("  nc-file  : %s", nc_path)
        log.info("  output   : %s", output_path)

        result = load_single_nc(nc_path)
        title  = args.title or f"FACTS — {nc_path.stem}"

        log.info("Year span : %s – %s  (%d time steps)",
                 result["years"][0], result["years"][-1], len(result["years"]))
        log.info("Building Bokeh dashboard ...")
        build_dashboard(
            result["data_dict"], result["years"],
            result["locations"], result["location_meta"],
            result["ssps"], result["wfs"],
            output_path, title=title,
            single_nc_mode=True,
        )
        log.info("Done.")
        return

    # ── Confidence file mode ─────────────────────────────────
    if args.confidence_root:
        conf_root = args.confidence_root.resolve()
        if not conf_root.is_dir():
            log.error("--confidence-root not found: %s", conf_root)
            sys.exit(1)

        default_out = conf_root / "facts_dashboard.html"
        output_path = (args.output or default_out).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info("FACTS Dashboard Generator — confidence file mode")
        log.info("  conf-root  : %s", conf_root)
        log.info("  conf-level : %s", args.confidence_level)
        log.info("  output     : %s", output_path)

        result = load_confidence_files(conf_root, args.confidence_level, args.location_lst)
        if args.confidence_level == "both":
            title = args.title or "FACTS — Low & Medium Confidence"
        else:
            title = args.title or f"FACTS — {args.confidence_level.replace('_', ' ').title()}"

        log.info("SSPs found : %s", result["ssps"])
        log.info("Year span  : %s – %s  (%d time steps)",
                 result["years"][0], result["years"][-1], len(result["years"]))
        log.info("Building Bokeh dashboard ...")
        build_dashboard(
            result["data_dict"], result["years"],
            result["locations"], result["location_meta"],
            result["ssps"], result["wfs"],
            output_path, title=title,
        )
        log.info("Done.")
        return

    # ── Multi-file / experiment-tree mode ────────────────────
    if not args.exp_root and not args.ssp_dirs:
        parser.error("Provide at least one of --exp-root, --ssp-dir, --single-nc-file, or --confidence-root")

    exp_root = args.exp_root.resolve() if args.exp_root else None
    if exp_root and not exp_root.is_dir():
        log.error("--exp-root not found: %s", exp_root)
        sys.exit(1)

    if exp_root:
        default_out = exp_root / "facts_dashboard.html"
    elif args.ssp_dirs:
        default_out = Path(args.ssp_dirs[0]).resolve() / "facts_dashboard.html"
    else:
        default_out = Path("facts_dashboard.html")
    output_path = (args.output or default_out).resolve()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("FACTS Dashboard Generator")
    if exp_root:
        log.info("  exp-root : %s", exp_root)
    for d in args.ssp_dirs:
        log.info("  ssp-dir  : %s", d)
    log.info("  output   : %s", output_path)

    log.info("Scanning for experiments ...")
    entries = collect_ssp_entries(exp_root=exp_root, ssp_dirs=args.ssp_dirs)
    if not entries:
        log.error("No SSP output directories with total .nc files found.")
        sys.exit(1)

    ssps = [e[0] for e in entries]
    wfs  = discover_workflows(entries)
    if not wfs:
        log.error("No workflow .nc files found.")
        sys.exit(1)

    locations = load_location_list(entries)

    log.info("SSPs found      : %s", ssps)
    log.info("Workflows found : %s", wfs)
    log.info("Locations       : %d tide gauge station(s)", len(locations))

    data_dict, years, location_meta = precompute_all(entries, wfs)
    if not data_dict:
        log.error("No data could be loaded from any .nc file.")
        sys.exit(1)

    title = args.title or "FACTS Sea-Level Projections"
    log.info("Year span : %s – %s  (%d time steps)", years[0], years[-1], len(years))
    log.info("Building Bokeh dashboard ...")
    build_dashboard(data_dict, years, locations, location_meta, ssps, wfs, output_path, title=title)
    log.info("Done.")


if __name__ == "__main__":
    main()
