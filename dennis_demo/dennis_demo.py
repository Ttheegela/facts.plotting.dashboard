#!/usr/bin/env python3
"""
dennis_demo.py — Single-file FACTS sea-level visualiser.

Reads one FACTS .nc file (must contain sea_level_change, years, locations),
computes p5/p17/p50/p83/p95 quantiles, and renders:
  1. A time-series line plot with shaded uncertainty bands
  2. An interactive grouped bar chart (one bar per percentile per year)
Output is a self-contained HTML file — no server needed.

Usage:
    python dennis_demo.py                          # uses bundled GrIS sample
    python dennis_demo.py path/to/your_file.nc
    python dennis_demo.py path/to/file.nc --output my_demo.html
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import xarray as xr
from bokeh.io import save
from bokeh.layouts import column, row
from bokeh.models import (
    CheckboxGroup,
    ColumnDataSource,
    CustomJS,
    Div,
    HoverTool,
    Legend,
    LegendItem,
    Span,
)
from bokeh.plotting import figure
from bokeh.resources import INLINE

# ── Default sample: SSP5-8.5, Greenland ice sheet, global mean ──────────────
_HERE = Path(__file__).parent
DEFAULT_NC = (
    _HERE
    / "../../factsIO/facts/exp.alt.emis/coupling.ssp585/output"
    / "coupling.ssp585.emuGrIS.emulandice.GrIS_globalsl.nc"
).resolve()

# ── Quantile config ──────────────────────────────────────────────────────────
QUANTILES = [0.05, 0.17, 0.50, 0.83, 0.95]
QUANTILE_LABELS = [
    "5th percentile",
    "17th percentile",
    "50th percentile (median)",
    "83rd percentile",
    "95th percentile",
]
# Cool (low) → warm (high) color gradient
QUANTILE_COLORS = ["#2166ac", "#92c5de", "#b2b2b2", "#f4a582", "#d6604d"]


# ── Data loading ─────────────────────────────────────────────────────────────

def compute_quantiles(nc_path: Path) -> dict:
    """
    Open a FACTS .nc file and compute 5 quantiles across the sample axis.

    Returns:
        years        — list of int year values
        q            — np.ndarray shape (5, n_years), location 0 only
        source_label — human-readable title string from file metadata
        baseyear     — int, reference year for anomalies
    """
    ds = xr.open_dataset(nc_path)
    if "sea_level_change" not in ds:
        raise KeyError(f"'sea_level_change' not found in {nc_path.name}")

    sl = ds["sea_level_change"].values          # (samples, years, locations)
    n_locs = sl.shape[2]
    if n_locs > 1:
        print(f"[dennis_demo] Note: {nc_path.name} has {n_locs} locations — "
              f"visualising location 0 only.")

    q = np.quantile(sl, QUANTILES, axis=0)     # (5, years, locations)
    q_loc0 = q[:, :, 0]                        # (5, years) — first location

    scenario = str(getattr(ds, "scenario", "unknown"))
    baseyear  = int(getattr(ds, "baseyear",  2005))
    source_label = (
        f"{nc_path.stem}  |  scenario: {scenario}  |  base year: {baseyear}"
    )
    return {
        "years":        ds.years.values.tolist(),
        "q":            q_loc0,
        "source_label": source_label,
        "baseyear":     baseyear,
    }


# ── Line plot builder ────────────────────────────────────────────────────────

def build_line_plot(years: list, q: np.ndarray, baseyear: int) -> object:
    """
    Time-series line plot with shaded uncertainty bands.

    Bands:
      - Light fill: p5 → p95  (outer uncertainty)
      - Medium fill: p17 → p83 (likely range)
      - Bold line: p50 median
      - Thin lines: p5 and p95 bounds
    """
    yr = years  # x-axis values (int years)

    p_line = figure(
        x_range=(min(yr) - 2, max(yr) + 2),
        width=1100,
        height=380,
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        y_axis_label=f"Sea Level Change (mm, relative to {baseyear})",
        x_axis_label="Year",
        title="Time Series — Uncertainty Projection",
    )
    p_line.title.text_font_size = "13px"
    p_line.yaxis.axis_label_text_font_size = "12px"
    p_line.xaxis.axis_label_text_font_size = "12px"
    p_line.grid.grid_line_color = "#e0e0e0"
    p_line.background_fill_color = "#fafafa"

    # Shaded bands (varea)
    p_line.varea(
        x=yr, y1=q[0].tolist(), y2=q[4].tolist(),
        fill_color="#aec7e8", fill_alpha=0.30,
        legend_label="5th – 95th pct (outer range)",
    )
    p_line.varea(
        x=yr, y1=q[1].tolist(), y2=q[3].tolist(),
        fill_color="#4292c6", fill_alpha=0.35,
        legend_label="17th – 83rd pct (likely range)",
    )

    # Bound lines (p5, p95) — thin dashed
    for qi, label in ((0, "5th pct"), (4, "95th pct")):
        p_line.line(
            x=yr, y=q[qi].tolist(),
            line_color=QUANTILE_COLORS[qi],
            line_width=1.2,
            line_dash="dashed",
            legend_label=label,
        )

    # Median line — bold
    src_med = ColumnDataSource(dict(x=yr, y=q[2].tolist()))
    med_r = p_line.line(
        x="x", y="y", source=src_med,
        line_color="#b2b2b2", line_width=2.8,
        legend_label="50th pct (median)",
    )
    p_line.scatter(
        x="x", y="y", source=src_med,
        size=6, color="#b2b2b2", legend_label="_nolegend_",
    )

    # Hover on median line
    hover_line = HoverTool(
        renderers=[med_r],
        tooltips=[("Year", "@x"), ("Median", "@y{0.1f} mm")],
        mode="vline",
    )
    p_line.add_tools(hover_line)

    # Zero baseline
    p_line.add_layout(Span(
        location=0, dimension="width",
        line_color="black", line_dash="solid", line_width=0.8, line_alpha=0.4,
    ))

    p_line.legend.location = "top_left"
    p_line.legend.label_text_font_size = "11px"
    p_line.legend.background_fill_alpha = 0.85
    p_line.legend.spacing = 4

    return p_line


# ── Dashboard builder ────────────────────────────────────────────────────────

def build_demo(nc_path: Path, output_path: Path) -> None:
    result   = compute_quantiles(nc_path)
    years    = result["years"]
    q        = result["q"]          # (5, n_years)
    n_years  = len(years)
    n_q      = len(QUANTILES)

    # ── Line plot ─────────────────────────────────────────────────────────
    p_line = build_line_plot(years, q, result["baseyear"])

    # ── Grouped bar geometry (mirrors _build_stacked_bar_section pattern) ──
    bar_w      = 0.12
    gap        = 0.30
    group_step = n_q * bar_w + gap
    half_group = (n_q * bar_w) / 2.0

    # Flat arrays: one entry per (year × quantile)
    xs, ys, colors, q_labels, year_labels, qi_index = [], [], [], [], [], []
    group_centers = []

    for yi, yr in enumerate(years):
        group_centers.append(yi * group_step)
        for qi in range(n_q):
            x = yi * group_step + qi * bar_w - half_group + bar_w / 2.0
            xs.append(x)
            ys.append(float(q[qi, yi]))
            colors.append(QUANTILE_COLORS[qi])
            q_labels.append(QUANTILE_LABELS[qi])
            year_labels.append(str(yr))
            qi_index.append(qi)

    source = ColumnDataSource(dict(
        x=xs, y=ys, colors=colors,
        q_labels=q_labels, year_labels=year_labels,
    ))

    # ── Figure ────────────────────────────────────────────────────────────
    x_end = n_years * group_step - gap / 2.0
    p = figure(
        x_range=(-group_step * 0.5, x_end),
        width=1100,
        height=500,
        title=result["source_label"],
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        y_axis_label=f"Sea Level Change (mm, relative to {result['baseyear']})",
        x_axis_label="Year",
    )
    p.title.text_font_size = "13px"
    p.yaxis.axis_label_text_font_size = "12px"
    p.xaxis.axis_label_text_font_size = "12px"

    bars = p.vbar(
        x="x", top="y", width=bar_w * 0.88,
        color="colors", source=source,
        line_color="white", line_width=0.5,
    )

    hover = HoverTool(renderers=[bars], tooltips=[
        ("Year",       "@year_labels"),
        ("Percentile", "@q_labels"),
        ("Value",      "@y{0.1f} mm"),
    ])
    p.add_tools(hover)

    # X-axis: one tick per year group, labelled with the year
    p.xaxis.ticker = group_centers
    p.xaxis.major_label_overrides = {
        c: str(years[i]) for i, c in enumerate(group_centers)
    }
    p.xaxis.major_label_orientation = 0.0

    p.grid.grid_line_color = "#e0e0e0"
    p.background_fill_color = "#fafafa"

    # ── Legend (dummy-renderer per quantile, same pattern as main dashboard) ─
    legend_items = []
    for qi in range(n_q):
        dummy_src = ColumnDataSource(dict(x=[0], y=[0]))
        dummy_r   = p.vbar(
            x="x", top="y", width=bar_w,
            color=QUANTILE_COLORS[qi],
            source=dummy_src, visible=False,
        )
        legend_items.append(LegendItem(
            label=QUANTILE_LABELS[qi],
            renderers=[dummy_r],
        ))
    legend = Legend(
        items=legend_items,
        title="Percentile",
        title_text_font_style="bold",
        label_text_font_size="12px",
        spacing=6,
    )
    p.add_layout(legend, "right")

    # ── CheckboxGroup — toggle individual percentiles ─────────────────────
    chk = CheckboxGroup(
        labels=QUANTILE_LABELS,
        active=list(range(n_q)),
        width=230,
    )

    cb = CustomJS(
        args=dict(
            source   = source,
            chk      = chk,
            all_x    = xs,
            all_y    = ys,
            all_colors  = colors,
            all_qlabels = q_labels,
            all_ylabels = year_labels,
            all_qi   = qi_index,
        ),
        code="""
const active = new Set(chk.active);
const nx = [], ny = [], nc = [], nq = [], ny2 = [];
for (let i = 0; i < all_x.length; i++) {
    if (active.has(all_qi[i])) {
        nx.push(all_x[i]);
        ny.push(all_y[i]);
        nc.push(all_colors[i]);
        nq.push(all_qlabels[i]);
        ny2.push(all_ylabels[i]);
    }
}
source.data = {x: nx, y: ny, colors: nc, q_labels: nq, year_labels: ny2};
source.change.emit();
""",
    )
    chk.js_on_change("active", cb)

    # ── Layout ────────────────────────────────────────────────────────────
    header = Div(text=f"""
<div style="font-family:Arial,sans-serif; margin-bottom:8px;">
  <span style="font-size:18px; font-weight:bold;">FACTS Sea-Level Projections — Single File Demo</span><br>
  <span style="font-size:12px; color:#555;">
    File: <code>{nc_path.name}</code> &nbsp;|&nbsp;
    {n_years} time steps &nbsp;|&nbsp;
    2,000 Monte Carlo samples &nbsp;|&nbsp;
    5 uncertainty percentiles
  </span>
</div>
""", width=1100)

    line_head = Div(text="""
<div style="font-family:Arial,sans-serif; margin-top:10px; margin-bottom:4px;">
  <b>Time Series</b> — shaded bands show outer (5th–95th) and likely (17th–83rd) uncertainty ranges.
  Hover on the median line for exact values.
</div>
""", width=1100)

    bar_head = Div(text="""
<div style="font-family:Arial,sans-serif; margin-top:24px; margin-bottom:4px;">
  <b>Grouped Bar Chart</b> — each group = one year, bars = individual percentiles (cool → warm).
  Toggle percentiles with the checkboxes below. Hover for exact values.
</div>
""", width=1100)

    chk_label = Div(
        text="<b style='font-size:12px;'>Show percentiles:</b>",
        width=160,
        styles={"padding-top": "6px"},
    )

    layout = column(
        header,
        line_head,
        p_line,
        bar_head,
        row(chk_label, chk),
        p,
    )

    save(layout, filename=str(output_path), resources=INLINE, title="FACTS Demo — Dennis")
    print(f"Saved → {output_path.resolve()}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="dennis_demo.py",
        description=(
            "Single-file FACTS sea-level visualiser. "
            "Pass one .nc file with sea_level_change, years, locations."
        ),
    )
    parser.add_argument(
        "nc_file", nargs="?",
        default=str(DEFAULT_NC),
        help="Path to a FACTS .nc file (default: bundled GrIS SSP5-8.5 sample)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output HTML path (default: dennis_demo.html next to this script)",
    )
    args = parser.parse_args()

    nc_path = Path(args.nc_file).resolve()
    if not nc_path.exists():
        print(f"ERROR: File not found: {nc_path}", file=sys.stderr)
        sys.exit(1)

    out = (args.output or _HERE / "dennis_demo.html").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    build_demo(nc_path, out)


if __name__ == "__main__":
    main()
