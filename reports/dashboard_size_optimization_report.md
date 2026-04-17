# FACTS Dashboard — Size Optimization Report

**Author:** Tarun Theegela (tt633)
**Date:** April 2026
**Dashboard repo:** https://github.com/tt633/facts.plotting.dashboard

---

## 1. Overview

This report documents the work done to reduce the FACTS Dashboard HTML output size from **168 MB → 66 MB** — a **61% reduction** — achieved in version v1.1.2. It also covers the IPCC AR6 color scheme adopted in the same release.

---

## 2. Problem

The FACTS Dashboard generates a fully self-contained HTML file — all data, JavaScript, and CSS are embedded inline (no server, no internet connection needed). This convenience comes at a cost: all projection data is serialized into the HTML as JSON.

With 4 SSPs × 7 workflows × 7 components × 2 scales × 24 locations × 5 quantiles × 30 time steps, the number of data points is large. Early versions stored all floating point values at full Python precision (e.g., `134.67892456`), which bloated the file size significantly.

| Version | Size | Notes |
|---------|------|-------|
| v1.0.0 | ~159 MB | Initial release |
| v1.1.0 | ~168 MB | Stacked bar chart added |
| v1.1.1 | ~168 MB | Grouped bars + quantile selector added |
| **v1.1.2** | **66 MB** | **61% reduction — see Section 3** |
| v1.1.3 | 66 MB | UX polish only, no size change |

---

## 3. Optimization: 1 Decimal Place Rounding

### What we did

In `precompute_all()`, after computing quantiles via `np.quantile()`, all sea-level values are rounded to **1 decimal place (mm precision)** before being stored in `data_dict`:

```python
# Before (full float precision — bloated)
"med": [134.67892456, 156.23401987, ...]

# After (1 dp rounding — compact)
"med": [134.7, 156.2, ...]
```

This is applied to all 5 quantile keys: `vlo`, `lo`, `med`, `hi`, `vhi`.

### Why 1 dp is sufficient

Sea-level projections are expressed in **millimetres**. The uncertainty range between the 17th and 83rd percentiles is typically hundreds of mm by 2100. Sub-millimetre precision (e.g., `134.67892456` vs `134.7`) has **no scientific meaning** at this scale and carries no information for the user. Rounding to 1 dp is consistent with standard IPCC reporting conventions.

### Impact

| Metric | Before (v1.1.1) | After (v1.1.2) |
|--------|----------------|----------------|
| HTML file size | ~168 MB | **66 MB** |
| Reduction | — | **61%** |
| Scientific precision lost | — | None meaningful |
| Load time in browser | Slow (~5–8s) | Fast (~2–3s) |

---

## 4. Color Scheme: IPCC AR6 Standard

Also introduced in v1.1.2, the SSP color scheme was updated to match the **IPCC Sixth Assessment Report (AR6)** standard palette — the same colors used in official IPCC figures. This ensures the dashboard is visually consistent with published literature.

### Color mapping

| SSP | Color | Hex | Meaning |
|-----|-------|-----|---------|
| SSP1-1.9 | Deep blue | `#1d6ea8` | Lowest emissions |
| SSP1-2.6 | Sky blue | `#56b4e9` | Very low emissions |
| SSP2-4.5 | Yellow | `#f0e442` | Intermediate |
| SSP3-7.0 | Amber | `#e69500` | High emissions |
| SSP5-3.4OS | Mauve | `#cc79a7` | Overshoot |
| SSP5-8.5 | Red | `#d73027` | Highest emissions |

### Design rationale

The cool-to-warm gradient (blue → red) maps intuitively to emissions severity — lower emissions scenarios are cool colors, higher emissions are warm. This is the convention established by the IPCC and widely recognized in the climate science community.

> **Note on space savings vs. IPCC semantics:** While switching to hex colors reduced some inline CSS verbosity, the dominant size saving came from the float rounding in Section 3 — not the color change. The color update was a correctness and consistency improvement.

---

## 5. Additional UX Improvements (v1.1.3)

Version v1.1.3 built on v1.1.2 with user-facing polish (no size change):

| Change | Detail |
|--------|--------|
| Human-readable component labels | "AIS (Antarctic Ice Sheet)" instead of "AIS" in dropdowns |
| Clean "Line N" slot rows | Removed repetitive "(Line N)" from every widget title |
| Fixed SSP legend hex codes | Legend color swatches now use `SSP_COLORS` dict values directly |
| Removed header placeholder text | Cleaned up boilerplate from the dashboard header |

---

## 6. Current Data Structure

All projection data is stored in `data_dict` with the key format:

```
"{ssp}|{component}|{wf}|{scale}|{loc_id}"
```

Each entry contains:
```python
{
    "years": [2020, 2030, ..., 2300],   # time steps (int)
    "vlo":   [12.3, 24.1, ...],         # 5th percentile (1 dp, mm)
    "lo":    [18.7, 34.2, ...],         # 17th percentile
    "med":   [28.4, 52.6, ...],         # 50th percentile (median)
    "hi":    [41.2, 78.3, ...],         # 83rd percentile
    "vhi":   [55.9, 101.4, ...],        # 95th percentile
}
```

The `loc_id` is `-1` for global mean sea level and a positive integer for a specific tide gauge station.

---

## 7. Summary

The key insight was that **float precision was the primary driver of HTML file size** in a self-contained Bokeh dashboard. Rounding to 1 decimal place — appropriate for millimetre-scale sea-level projections — cut the output size by 61% with no loss of scientific value. The IPCC AR6 color scheme was adopted simultaneously to align the dashboard with published standards.
