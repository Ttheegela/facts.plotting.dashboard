#!/usr/bin/env python3
"""
facts_dashboard.py — FACTS Sea-Level Projection Dashboard Generator
Version: 1.1.3

Generates a fully self-contained, interactive HTML dashboard from FACTS output
.nc files. No server required — open the HTML in any browser.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Python ≥ 3.9
  bokeh >= 3.4    xarray >= 2023    numpy >= 1.24
  pandas >= 2.0   netCDF4 >= 1.6

  Install:  pip install bokeh xarray numpy pandas netCDF4

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
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr            # reads NetCDF4 files as labelled arrays

# Bokeh: browser-side interactive plots baked into a single HTML file (no server needed)
from bokeh.io import save
from bokeh.layouts import column, row
from bokeh.models import (
    Checkbox, ColumnDataSource, CustomJS, DataTable, Div,
    HTMLTemplateFormatter, HoverTool, Range1d, RangeSlider, Select, TableColumn,
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
    "ssp119": "#1d6ea8",   # deep blue  — lowest emissions
    "ssp126": "#56b4e9",   # sky blue
    "ssp245": "#f0e442",   # yellow
    "ssp370": "#e69500",   # amber/orange
    "ssp534": "#cc79a7",   # mauve
    "ssp585": "#d73027",   # red        — highest emissions
    "H.ssp370": "#e9a3c9",   
}
_FALLBACK_COLORS = ["#4dac26", "#b8e186", "#f7f7f7", "#e9a3c9", "#c51b7d", "#542788"]

SSP_LABELS = {
    "ssp119": "SSP1-1.9",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0",
    "ssp585": "SSP5-8.5",
    "ssp534": "SSP5-3.4 overshoot",
    "H.ssp370": "H.ssp370",
}

WF_LABELS = {
    "wf1e": "wf1e — emulandice AIS+GrIS, emulandice glaciers (to 2100)",
    "wf1f": "wf1f — FittedISMIP GrIS, AR5 AIS+glaciers (to 2300)",
    "wf2e": "wf2e — emulandice GrIS, LARMIP AIS, emulandice glaciers (to 2100)",
    "wf2f": "wf2f — FittedISMIP GrIS, LARMIP AIS, AR5 glaciers (to 2300)",
    "wf3e": "wf3e — emulandice GrIS, DeConto21 AIS, emulandice glaciers (to 2100)",
    "wf3f": "wf3f — FittedISMIP GrIS, DeConto21 AIS, AR5 glaciers (to 2300)",
    "wf4":  "wf4  — Bamber19 ice sheets, AR5 glaciers (to 2300)",
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

# Fixed slider bounds
XMIN_FIXED = 2020
XMAX_FIXED = 2300
YMIN_FIXED = -500
YMAX_FIXED = 6000

# ─────────────────────────────────────────────────────────
# Discovery helpers
# ─────────────────────────────────────────────────────────

def _count_nc_locations(out_dir: Path) -> int:
    """
    Return the number of tide gauge locations in the first available
    *.total.workflow.*.local*.nc file found in out_dir.
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
    
def _parse_run_prefix_and_ssp(nc_path: Path) -> tuple[str, str]:
    """
    Examples
    --------
    coupling.ssp126.total.workflow.wf1e.local.nc   -> ("coupling.ssp126", "ssp126")
    coupling.ssp126.total.workflow.wf1e.localsl.nc -> ("coupling.ssp126", "ssp126")
    src.H.ssp370.total.workflow.wf1e.local.nc      -> ("src.H.ssp370", "H.ssp370")
    src.H.ssp370.total.workflow.wf1e.localsl.nc    -> ("src.H.ssp370", "H.ssp370")
    """
    stem = nc_path.stem
    marker = ".total.workflow."
    if marker not in stem:
        raise ValueError(f"Cannot parse run prefix from {nc_path.name}")
    run_prefix = stem.split(marker, 1)[0]
    parts = run_prefix.split(".")
    ssp_tag = ".".join(parts[1:]) if len(parts) > 1 else run_prefix
    return run_prefix, ssp_tag


def _build_nc_path(out_dir: Path, run_prefix: str, suffix: str) -> Path:
    """
    Build a file path using the discovered run prefix.

    Example
    -------
    run_prefix = "src.H.ssp370"
    suffix     = "ocean.tlm.sterodynamics_globalsl.nc"
    result     = out_dir / "src.H.ssp370.ocean.tlm.sterodynamics_globalsl.nc"
    """
    return out_dir / f"{run_prefix}.{suffix}"


def _resolve_total_nc(out_dir: Path, run_prefix: str, wf: str, scale: str) -> Path:
    """
    Accept either:
      ...total.workflow.wf1e.local.nc
      ...total.workflow.wf1e.localsl.nc
      ...total.workflow.wf1e.global.nc
      ...total.workflow.wf1e.globalsl.nc
    """
    hits = sorted(out_dir.glob(f"{run_prefix}.total.workflow.{wf}.{scale}*.nc"))
    if hits:
        return hits[0]
    return out_dir / f"{run_prefix}.total.workflow.{wf}.{scale}.nc"



def collect_ssp_entries(exp_root: Path = None, ssp_dirs: list = None) -> list:
    """
    Returns a list of (ssp_tag, run_prefix, output_dir, exp_dir) tuples.

    Examples
    --------
    coupling.ssp126.total.workflow... -> ("ssp126", "coupling.ssp126", ...)
    src.H.ssp370.total.workflow...    -> ("H.ssp370", "src.H.ssp370", ...)
    """
    entries   = []
    seen_tags = set()

    def _maybe_add_entry(exp_dir: Path, out_dir: Path):
        nonlocal entries, seen_tags

        if not out_dir.is_dir():
            return

        nc_files = sorted(out_dir.glob("*.total.workflow.*.nc"))
        if not nc_files:
            return

        try:
            run_prefix, tag = _parse_run_prefix_and_ssp(nc_files[0])
        except Exception as exc:
            log.warning("Could not parse run prefix in %s: %s", out_dir, exc)
            return

        if tag in seen_tags:
            log.warning("SSP %s already added — skipping %s", tag, out_dir)
            return

        entries.append((tag, run_prefix, out_dir, exp_dir))
        seen_tags.add(tag)
        log.info("Found SSP %s (prefix=%s) in %s", tag, run_prefix, out_dir)

    if exp_root:
        for d in sorted(exp_root.iterdir()):
            if not d.is_dir():
                continue

            out = d / "output" if (d / "output").is_dir() else d
            if not any(out.glob("*.total.workflow.*.nc")):
                continue

            out_copy = d / "output copy"
            if out_copy.is_dir() and any(out_copy.glob("*.total.workflow.*.nc")):
                n_out  = _count_nc_locations(out)
                n_copy = _count_nc_locations(out_copy)
                if n_copy > n_out:
                    log.info(
                        "Preferring 'output copy' for %s (%d locs > %d locs in output/)",
                        d.name, n_copy, n_out
                    )
                    out = out_copy

            _maybe_add_entry(d, out)

    for raw in (ssp_dirs or []):
        p = Path(raw).resolve()

        if p.name == "output" and p.is_dir():
            out_dir = p
            exp_dir = p.parent
        elif (p / "output").is_dir():
            out_dir = p / "output"
            exp_dir = p
        else:
            out_dir = p
            exp_dir = p.parent

        _maybe_add_entry(exp_dir, out_dir)

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
            df = pd.read_csv(p, sep=r"\s+", header=None, names=["name", "id", "lat", "lon"])
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
        def _r1(arr): return [round(float(v), 1) for v in arr]
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


def precompute_all(entries: list, wfs: list) -> tuple:
    """
    Load all total + component .nc files and compute quantiles.

    Data dict keys:
      total     → "{ssp}|total|{wf}|{scale}|{loc_id}"
      component → "{ssp}|{component}|{wf}|{scale}|{loc_id}"
                  (same data stored under every wf so JS lookup is uniform)

    Args:
        entries: List of (ssp_tag, run_prefix, output_dir, exp_dir) tuples.
        wfs:     List of workflow IDs.

    Returns:
        (data_dict, years_ref, location_meta)
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
                        fallback = (
                            WORKFLOW_COMPONENT_FALLBACK_SUM
                            .get(wf, {})
                            .get(comp, {})
                            .get(scale)
                        )
                        if fallback:
                            fb_paths = [
                                _build_nc_path(out_dir, run_prefix, p.format(scale=scale))
                                for p in fallback
                            ]
                            if all(p.exists() for p in fb_paths):
                                log.debug("  Fallback sum: %s", [p.name for p in fb_paths])
                                try:
                                    result = compute_quantiles_sum(fb_paths)
                                except Exception as exc:
                                    log.warning(
                                        "Failed fallback sum %s|%s|%s|%s: %s",
                                        ssp, comp, wf, scale, exc
                                    )
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
    "dotdash":  "⋅ — ⋅ —",
    "dashdot":  "— ⋅ — ⋅",
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
# TABLE section builder
# ─────────────────────────────────────────────────────────

def _build_table_section(
    data_dict:       dict,
    years:           list,
    ssps:            list,
    wfs:             list,
    loc_options_all: list,
    location_meta_js: dict,
) -> object:
    """
    Build the interactive TABLE section (Bokeh DataTable).

    Rows = workflows, columns = SSPs.
    Each cell shows: median / (p17, p83) / [p5, p95] for the selected
    year, scale, and location.  Uses component='total' only.

    Args:
        data_dict:        Full data dict keyed by {ssp}|{component}|{wf}|{scale}|{loc_id}.
        years:            Full year list (used to build the year selector options).
        ssps:             List of SSP tag strings.
        wfs:              List of workflow ID strings.
        loc_options_all:  (value, label) pairs for the location Select widget.
        location_meta_js: JS-side location metadata dict.

    Returns:
        Bokeh Column layout containing the table header, controls, and DataTable.

    Example:
        tbl = _build_table_section(data_dict, years, ssps, wfs, loc_opts, loc_meta)
    """
    # ── Pre-populate table for default selections ─────────
    # This makes values visible immediately on page load without
    # requiring the user to interact with a widget first.
    default_year_int  = 2100
    default_scale     = "local"
    default_loc_int   = int(loc_options_all[1][0]) if len(loc_options_all) > 1 else int(loc_options_all[0][0])

    def _table_row(wf, year_int, scale, loc_int):
        row_vals = {}
        # For global scale the nc file only contains loc_id = -1
        lookup_loc = -1 if scale == "global" else loc_int
        for ssp in ssps:
            key = f"{ssp}|total|{wf}|{scale}|{lookup_loc}"
            d   = data_dict.get(key)
            if not d:
                row_vals[ssp] = ""
                continue
            try:
                idx = d["years"].index(year_int)
            except ValueError:
                row_vals[ssp] = ""
                continue
            med = d["med"][idx]; lo = d["lo"][idx]; hi = d["hi"][idx]
            vlo = d["vlo"][idx]; vhi = d["vhi"][idx]
            row_vals[ssp] = f"{med:.1f}\n({lo:.1f}, {hi:.1f})\n[{vlo:.1f}, {vhi:.1f}]"
        return row_vals

    init_data = {"workflow": [wf for wf in wfs]}
    for ssp in ssps:
        init_data[ssp] = []
    for wf in wfs:
        row_vals = _table_row(wf, default_year_int, default_scale, default_loc_int)
        for ssp in ssps:
            init_data[ssp].append(row_vals[ssp])

    source_table = ColumnDataSource(data=init_data)

    # ── TableColumns ─────────────────────────────────────
    html_fmt = HTMLTemplateFormatter(template='<div style="white-space:pre-line;"><%= value %></div>')
    tbl_columns = [
        TableColumn(field="workflow", title="Workflow",
                    formatter=HTMLTemplateFormatter(
                        template='<div style="font-weight:bold;"><%= value %></div>'
                    )),
    ]
    for ssp in ssps:
        tbl_columns.append(TableColumn(field=ssp, title=ssp, formatter=html_fmt, width=200))

    data_table = DataTable(
        source=source_table,
        columns=tbl_columns,
        width=900,
        height=min(600, 80 + 80 * len(wfs)),
        row_height=80,
        index_position=None,
        editable=False,
    )

    # ── Controls ──────────────────────────────────────────
    year_opts    = [str(y) for y in sorted(set(years))]
    default_year = str(default_year_int) if str(default_year_int) in year_opts else year_opts[-1]
    default_loc  = str(default_loc_int)

    year_sel  = Select(title="Year (Table)",     value=default_year,  options=year_opts,      width=120)
    scale_sel = Select(title="Scale (Table)",    value=default_scale, options=[("local","Local RSL"),("global","Global Mean SL")], width=160)
    loc_sel   = Select(title="Location (Table)", value=default_loc,   options=loc_options_all, width=280)

    # ── CustomJS callback ─────────────────────────────────
    # Key format: "{ssp}|{component}|{wf}|{scale}|{loc_id}"
    # component is always "total" in this (workflow summary) table.
    # The workflow table iterates over wfs (rows) and ssps (columns).
    JS_TABLE = """
    const year_val  = parseInt(year_sel.value);
    const scale_val = scale_sel.value;
    // Global .nc files only contain loc_id = -1; local files use the tide gauge ID.
    // This mirrors how Python's _store_result() writes keys.
    const loc_val   = (scale_val === "global") ? -1 : parseInt(loc_sel.value);
    const component = "total";

    const new_data = { workflow: [] };
    for (let j = 0; j < ssps.length; j++) { new_data[ssps[j]] = []; }

    for (let i = 0; i < wfs.length; i++) {
        const wf = wfs[i];
        new_data.workflow.push(wf.startsWith("wf") ? wf : "wf" + wf);
        for (let j = 0; j < ssps.length; j++) {
            const ssp = ssps[j];
            const key = ssp + "|" + component + "|" + wf + "|" + scale_val + "|" + loc_val;
            const d   = data_dict[key];
            if (!d) { new_data[ssp].push(""); continue; }
            const idx = d.years.indexOf(year_val);
            if (idx === -1) { new_data[ssp].push(""); continue; }
            const med = d.med[idx], lo = d.lo[idx], hi = d.hi[idx];
            const vlo = (d.vlo !== undefined) ? d.vlo[idx] : null;
            const vhi = (d.vhi !== undefined) ? d.vhi[idx] : null;
            let cell = med.toFixed(1) + "\\n(" + lo.toFixed(1) + ", " + hi.toFixed(1) + ")";
            if (vlo !== null && vhi !== null) {
                cell += "\\n[" + vlo.toFixed(1) + ", " + vhi.toFixed(1) + "]";
            }
            new_data[ssp].push(cell);
        }
    }
    source_table.data = new_data;
    source_table.change.emit();
    """

    cb = CustomJS(
        args=dict(
            source_table=source_table,
            data_dict=data_dict,
            year_sel=year_sel,
            scale_sel=scale_sel,
            loc_sel=loc_sel,
            ssps=ssps,
            wfs=wfs,
        ),
        code=JS_TABLE,
    )
    year_sel.js_on_change("value",  cb)
    scale_sel.js_on_change("value", cb)
    loc_sel.js_on_change("value",   cb)

    # ── Header ────────────────────────────────────────────
    tbl_head = Div(text="""
<div style="margin-top:32px;margin-bottom:6px;">
  <u>FACTS <b>sea-level projections</b></u> (TABLE)<br>
  Select a <b>year</b>, <b>scale</b> (local/global), and <b>location</b> to view
  <u>median</u>, <u>[17th, 83rd]</u>, and <u>[5th, 95th]</u> percentile values
  for all workflows and SSPs.<br>
  Rows show workflows, columns show SSPs.
</div>
""", width=900)

    return column(tbl_head, row(year_sel, scale_sel, loc_sel), data_table)


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
    default_scale    = "global"
    default_loc_int  = -1   # global mean SL — matches professor's reference table default
    comps = COMPONENTS      # [total, AIS, GrIS, glaciers, sterodynamics, landwaterstorage, vlm]

    def _comp_cell(comp, wf, year_int, scale, loc_int):
        lookup_loc = -1 if scale == "global" else loc_int
        key = f"{wf_to_ssp_key(comp, wf, scale, lookup_loc)}"  # placeholder; filled per SSP below
        # (actual per-SSP lookup done in the loop below)
        return None  # unused; loop below handles it

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
    loc_sel  = Select(title="Location (local)", value=str(default_loc_int),
                      options=loc_options_all, width=280)

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

    const new_data = { component: comps.slice() };
    for (let j = 0; j < ssps.length; j++) { new_data[ssps[j]] = []; }

    for (let i = 0; i < comps.length; i++) {
        const comp = comps[i];
        for (let j = 0; j < ssps.length; j++) {
            const ssp = ssps[j];
            const key = ssp + "|" + comp + "|" + wf_val + "|" + scale_val + "|" + loc_val;
            const d   = data_dict[key];
            if (!d) { new_data[ssp].push(""); continue; }
            const idx = d.years.indexOf(year_val);
            if (idx === -1) { new_data[ssp].push(""); continue; }
            const med = d.med[idx], lo = d.lo[idx], hi = d.hi[idx];
            const vlo = (d.vlo !== undefined) ? d.vlo[idx] : null;
            const vhi = (d.vhi !== undefined) ? d.vhi[idx] : null;
            let cell = med.toFixed(1) + "\\n(" + lo.toFixed(1) + ", " + hi.toFixed(1) + ")";
            if (vlo !== null && vhi !== null) {
                cell += "\\n[" + vlo.toFixed(1) + ", " + vhi.toFixed(1) + "]";
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
            data_dict=data_dict,
            wf_sel=wf_sel, year_sel=year_sel,
            scale_sel=scale_sel, loc_sel=loc_sel,
            ssps=ssps, comps=comps,
        ),
        code=JS_COMP,
    )
    wf_sel.js_on_change("value",    cb)
    year_sel.js_on_change("value",  cb)
    scale_sel.js_on_change("value", cb)
    loc_sel.js_on_change("value",   cb)

    comp_head = Div(text="""
<div style="margin-top:32px;margin-bottom:6px;">
  <u>FACTS <b>sea-level projections — by component</b></u> (TABLE)<br>
  Select a <b>workflow</b>, <b>year</b>, <b>scale</b>, and <b>location</b> to view
  <u>median</u>, <u>(17th, 83rd)</u>, and <u>[5th, 95th]</u> percentile values
  for each sea-level component and SSP.
  &nbsp; Scale: Global Mean SL uses loc&nbsp;=&nbsp;−1; Local RSL uses the selected tide gauge.
</div>
""", width=900)

    return column(comp_head, row(wf_sel, year_sel, scale_sel, loc_sel), data_table)


def _build_stacked_bar_section(
    data_dict:        dict,
    years:            list,
    ssps:             list,
    wfs:              list,
    loc_options_all:  list,
    location_meta_js: dict,
) -> object:
    """
    Build the grouped bar chart section.

    X-axis  = all tide gauge locations; within each group one bar per SSP scenario
    Y-axis  = RSL (mm) at selected quantile, workflow, component, scale, year
    Colors  = one colour per SSP (consistent with line plot palette)

    Controls: workflow, component, scale, year, quantile.
    HoverTool shows location name, coords, SSP label, and value.
    """
    SSP_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp534", "ssp585"]
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
    # Each location group occupies (n_ssps * bar_width + gap).
    # Bar i within group j sits at: j * group_step + i * bar_width - half_group
    bar_w      = 0.15
    gap        = 0.25
    group_step = n_ssps * bar_w + gap
    half_group = (n_ssps * bar_w) / 2.0

    def _bar_x(loc_idx, ssp_idx):
        return loc_idx * group_step + ssp_idx * bar_w - half_group + bar_w / 2.0

    group_centers = [i * group_step for i in range(n_locs)]

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

    init_data  = _build_arrays(default_comp, default_wf, default_scale,
                               default_year, default_q_key)
    source_bar = ColumnDataSource(data=init_data)

    # -- Figure --
    x_end = n_locs * group_step - gap / 2.0
    p_bar = figure(
        x_range=(-group_step * 0.3, x_end),
        width=1200,
        height=520,
        title=(
            f"RSL Projections at {default_year} — SSP Comparison per Tide Gauge"
            f"  ({default_wf}, {default_comp}, {default_scale}, median)"
        ),
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        y_axis_label="RSL Change (mm)",
        x_axis_label="Tide Gauge",
    )

    hover = HoverTool(tooltips=[
        ("Location", "@loc_names"),
        ("SSP",      "@ssp_labels"),
        ("Value",    "@y{0.1f} mm"),
        ("Lat",      "@loc_lat"),
        ("Lon",      "@loc_lon"),
    ])
    p_bar.add_tools(hover)

    p_bar.vbar(x="x", top="y", width=bar_w * 0.9, color="colors",
               source=source_bar, line_color="white", line_width=0.5)

    # x-axis: one tick per location group, labelled with location name
    p_bar.xaxis.ticker = group_centers
    p_bar.xaxis.major_label_overrides = {c: loc_names[i] for i, c in enumerate(group_centers)}
    p_bar.xaxis.major_label_orientation = 1.0

    # -- Legend: one entry per SSP (manual, outside plot) --
    from bokeh.models import Legend, LegendItem, GlyphRenderer
    legend_items = []
    for si, ssp in enumerate(plot_ssps):
        color = SSP_COLORS.get(ssp, _FALLBACK_COLORS[si % len(_FALLBACK_COLORS)])
        dummy_src = ColumnDataSource(data=dict(x=[0], y=[0]))
        dummy_r   = p_bar.vbar(x="x", top="y", width=bar_w, color=color,
                               source=dummy_src, visible=False)
        legend_items.append(LegendItem(label=SSP_LABELS.get(ssp, ssp), renderers=[dummy_r]))
    legend = Legend(items=legend_items, title="SSP Scenario",
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

    # -- CustomJS callback --
    Q_LABELS_JS = {v: lbl for v, lbl in q_opts}

    JS_BAR = """
    const wf    = wf_sel.value;
    const comp  = comp_sel.value;
    const scale = scale_sel.value;
    const year  = parseInt(year_sel.value);
    const q_key = q_sel.value;

    const xs = [], ys = [], colors = [], ssp_labels = [];
    const loc_names = [], loc_ids = [], loc_lat = [], loc_lon = [];

    for (let li = 0; li < n_locs; li++) {
        const loc_id = (scale === "global") ? -1 : loc_ids_arr[li];
        for (let si = 0; si < plot_ssps.length; si++) {
            const ssp = plot_ssps[si];
            const x   = li * group_step + si * bar_w - half_group + bar_w / 2.0;
            const key = ssp + "|" + comp + "|" + wf + "|" + scale + "|" + loc_id;
            const d   = data_dict[key];
            let   val = 0.0;
            if (d) {
                const idx = d.years.indexOf(year);
                if (idx !== -1 && d[q_key] !== undefined) val = d[q_key][idx];
            }
            xs.push(x);
            ys.push(val);
            colors.push(ssp_color_map[ssp]);
            ssp_labels.push(ssp_label_map[ssp] || ssp);
            loc_names.push(loc_names_arr[li]);
            loc_ids.push(String(loc_ids_arr[li]));
            loc_lat.push(loc_lat_arr[li]);
            loc_lon.push(loc_lon_arr[li]);
        }
    }

    source_bar.data = {
        x: xs, y: ys, colors: colors, ssp_labels: ssp_labels,
        loc_names: loc_names, loc_ids: loc_ids,
        loc_lat: loc_lat, loc_lon: loc_lon,
    };
    source_bar.change.emit();

    const q_label = q_label_map[q_key] || q_key;
    p_bar.title.text = "RSL Projections at " + year +
        " — SSP Comparison per Tide Gauge" +
        "  (" + wf + ", " + comp + ", " + scale + ", " + q_label + ")";
    """

    cb = CustomJS(
        args=dict(
            source_bar  = source_bar,
            data_dict   = data_dict,
            p_bar       = p_bar,
            wf_sel      = wf_sel,
            comp_sel    = comp_sel,
            scale_sel   = scale_sel,
            year_sel    = year_sel,
            q_sel       = q_sel,
            plot_ssps   = plot_ssps,
            loc_ids_arr = loc_ids,
            loc_names_arr = loc_names,
            loc_lat_arr = loc_lat,
            loc_lon_arr = loc_lon,
            n_locs      = n_locs,
            bar_w       = bar_w,
            group_step  = group_step,
            half_group  = half_group,
            ssp_color_map  = {s: SSP_COLORS.get(s, _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
                              for i, s in enumerate(plot_ssps)},
            ssp_label_map  = {s: SSP_LABELS.get(s, s) for s in plot_ssps},
            q_label_map    = Q_LABELS_JS,
        ),
        code=JS_BAR,
    )
    wf_sel.js_on_change("value",    cb)
    comp_sel.js_on_change("value",  cb)
    scale_sel.js_on_change("value", cb)
    year_sel.js_on_change("value",  cb)
    q_sel.js_on_change("value",     cb)

    bar_head = Div(text="""
<div style="margin-top:32px;margin-bottom:6px;">
  <u>FACTS <b>sea-level projections — SSP comparison</b></u> (GROUPED BAR CHART)<br>
  Each group = one tide gauge location. Bars within each group = SSP scenarios side by side.<br>
  Select <b>workflow</b>, <b>component</b>, <b>scale</b>, <b>year</b>, and <b>quantile</b>.
  Hover over any bar for location details and RSL value (mm).
  Click legend items to show/hide individual scenarios.
</div>
""", width=1200)

    return column(bar_head, row(wf_sel, comp_sel, scale_sel, year_sel, q_sel), p_bar)


def wf_to_ssp_key(comp, wf, scale, loc):
    """
    Dead stub — not called at runtime.

    The pre-populate loop in _build_component_table_section() calls this function
    syntactically but immediately discards the return value.  The actual per-SSP key
    is built inline in that loop.  Kept here to make the loop readable without an
    unexplained `None` return.
    """
    return ""


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
):
    """
    Build and save the Bokeh interactive dashboard HTML.

    Args:
        data_dict:     Keyed by "{ssp}|{component}|{wf}|{scale}|{loc_id}".
        years:         Reference year list for axis range.
        locations:     List of dicts from location.lst (name, id, lat, lon).
        location_meta: Dict of {int loc_id: {lat, lon}}.
        ssps:          List of SSP tag strings.
        wfs:           List of workflow ID strings.
        output_path:   Path to write the output HTML file.
        title:         Dashboard title string.

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
    first_loc = str(all_loc_ids[1]) if len(all_loc_ids) > 1 else str(all_loc_ids[0])
    slot_defaults = []
    for i in range(6):
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
        sources.append(ColumnDataSource(data=dict(
            years=d["years"], med=d["med"], lo=d["lo"], hi=d["hi"],
        )))

    # ── Y range from data ──────────────────────────────────
    all_lo = [v for d in data_dict.values() for v in d["lo"] if v is not None]
    all_hi = [v for d in data_dict.values() for v in d["hi"] if v is not None]
    ymin_data   = float(min(all_lo)) if all_lo else YMIN_FIXED
    ymax_data   = float(max(all_hi)) if all_hi else YMAX_FIXED
    y_pad       = 0.05 * (ymax_data - ymin_data)
    y_init_min  = max(YMIN_FIXED, ymin_data - y_pad)
    y_init_max  = min(YMAX_FIXED, ymax_data + y_pad)
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
    for i, sd in enumerate(slot_defaults):
        color = ssp_color(sd["ssp"], i)
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
        wf_sel   = Select(title="Workflow",   value=sd["wf"],    options=wf_opts,    width=170)
        ssp_sel  = Select(title="SSP",        value=sd["ssp"],   options=ssp_opts,   width=140)
        comp_sel = Select(title="Component",  value=sd["comp"],  options=comp_opts,  width=200)
        scale_sel= Select(title="Scale",      value=sd["scale"], options=scale_opts, width=140)
        loc_sel  = Select(title="Location",   value=sd["loc"],   options=loc_options_all, width=240)

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
            "color_box": color_box, "style_box": style_box,
            "loc_info": loc_info_div, "chk": chk, "row_label": row_label,
        })

    # ── CustomJS callbacks ─────────────────────────────────
    # JS_UPDATE fires when any selector (workflow, SSP, component, scale, location) changes.
    # Key format must match Python's _store_result: "{ssp}|{comp}|{wf}|{scale}|{loc_id}"
    # loc.value is "-1" for Global Mean SL; a positive integer string for a tide gauge.
    JS_UPDATE = """
    const key = ssp.value + "|" + comp.value + "|" + wf.value + "|" + scale.value + "|" + loc.value;
    const d   = data_dict[key];

    if (!d) {
        console.warn("No data for key:", key);
        // Clear the ColumnDataSource so stale data from a previous selection is not shown.
        // (e.g. VLM has no global variant — switching to global must blank the plot, not leave
        //  the previous local VLM curve visible)
        source.data = { years: [], med: [], lo: [], hi: [] };
        source.change.emit();
        band.visible = r_solid.visible = r_dashed.visible = r_dotted.visible =
        r_circle.visible = r_diamond.visible = r_asterisk.visible = r_triangle.visible = false;
    } else {
        source.data = { years: d.years, med: d.med, lo: d.lo, hi: d.hi };
        source.change.emit();

        // Colour from SSP
        const c = ssp_colors[ssp.value] || "black";
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
            data_dict=data_dict,
            wf=sw["wf"], ssp=sw["ssp"], comp=sw["comp"],
            scale=sw["scale"], loc=sw["loc"],
            chk=sw["chk"],
            band=sr["band"], r_solid=sr["solid"], r_dashed=sr["dashed"],
            r_dotted=sr["dotted"], r_circle=sr["circle"], r_diamond=sr["diamond"],
            r_asterisk=sr["asterisk"], r_triangle=sr["triangle"],
            ssp_colors=SSP_COLORS,
            comp_styles=COMPONENT_STYLES,
            color_box=sw["color_box"],
            style_box=sw["style_box"],
            style_preview_map=style_preview_map_js,
            loc_info=sw["loc_info"],
            location_meta=location_meta_js,
        )
        cb_update = CustomJS(args=common, code=JS_UPDATE)
        cb_vis    = CustomJS(args=common, code=JS_VISIBILITY)

        for sel in (sw["wf"], sw["ssp"], sw["comp"], sw["scale"], sw["loc"]):
            sel.js_on_change("value", cb_update)
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
        title="Y range (mm)",
        start=YMIN_FIXED, end=YMAX_FIXED,
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

    # ── Layout rows ────────────────────────────────────────
    ctrl_rows = []
    for sw in slot_widgets:
        ctrl_rows.append(row(
            sw["row_label"],
            sw["wf"], sw["ssp"], sw["color_box"],
            sw["comp"], sw["style_box"],
            sw["scale"],
            sw["loc"], sw["loc_info"], sw["chk"],
        ))
    controls_block = column(*ctrl_rows, x_slider, y_slider)

    # ── Header ─────────────────────────────────────────────
    desc_head = Div(text=f"""
<div style="margin-bottom:8px;">
<br>
  <u>FACTS <b>sea-level projections</b></u><br>
  <b>{title}</b><br><br>
  Select a <b>workflow</b>, <b>SSP</b> and <b>Component</b> to view
  <u>median</u> (p50) and <u>17th&#8211;83rd percentile</u> (shading).<br>
  For a description of <b>Workflows</b>, see the table below.
</div>
""", width=900)

    # ── Legend ─────────────────────────────────────────────
    legend_html = """
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
    <b>SSP colours:</b> &nbsp;
    <span style="color:#1d6ea8">&#9632;</span> SSP1-1.9 &nbsp;
    <span style="color:#56b4e9">&#9632;</span> SSP1-2.6 &nbsp;
    <span style="color:#f0e442">&#9632;</span> SSP2-4.5 &nbsp;
    <span style="color:#e69500">&#9632;</span> SSP3-7.0 &nbsp;
    <span style="color:#d73027">&#9632;</span> SSP5-8.5 &nbsp;
    <span style="color:#cc79a7">&#9632;</span> SSP5-3.4OS
  </div>
</div>
"""
    text_legend = Div(text=legend_html, width=900)

    # ── Citation + workflow table ───────────────────────────
    citation = Div(text=f"""
<div style="margin-bottom:8px;">
<br>
  Generated by <code>facts_dashboard.py</code>.
  Values in <b>mm</b> relative to the experiment base year. Shading = p17&#8211;p83.
  {_workflow_table_html()}
</div>
""", width=900)

    # ── STACKED BAR section ────────────────────────────────
    stacked_bar_section = _build_stacked_bar_section(
        data_dict, years, ssps, wfs, loc_options_all, location_meta_js,
    )

    # ── TABLE section ──────────────────────────────────────
    comp_table_section = _build_component_table_section(
        data_dict, years, ssps, wfs, loc_options_all, location_meta_js,
    )

    dashboard = column(
        desc_head, controls_block, p, text_legend,
        stacked_bar_section,
        comp_table_section,
        citation,
    )
    save(dashboard, filename=str(output_path), resources=INLINE, title=title)
    log.info("Dashboard saved → %s", output_path.resolve())

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
    parser.add_argument("--output", type=Path, default=None, metavar="FILE",
                        help="Output HTML path (default: facts_dashboard.html next to exp-root)")
    parser.add_argument("--title", default="FACTS Sea-Level Projections",
                        help="Dashboard title shown in the header")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable DEBUG-level logging")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if not args.exp_root and not args.ssp_dirs:
        parser.error("Provide at least one of --exp-root or --ssp-dir")

    exp_root = args.exp_root.resolve() if args.exp_root else None
    if exp_root and not exp_root.is_dir():
        log.error("--exp-root not found: %s", exp_root)
        sys.exit(1)

    default_out = (exp_root / "facts_dashboard.html") if exp_root else Path("facts_dashboard.html")
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

    log.info("Year span : %s – %s  (%d time steps)", years[0], years[-1], len(years))
    log.info("Building Bokeh dashboard ...")
    build_dashboard(data_dict, years, locations, location_meta, ssps, wfs, output_path, title=args.title)
    log.info("Done.")


if __name__ == "__main__":
    main()
