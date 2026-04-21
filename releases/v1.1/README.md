# v1.1 — Stacked Bar Chart

**Script:** [`facts_dashboard_v1.1.py`](./facts_dashboard_v1.1.py)

## What is new in v1.1

### Stacked bar chart

A stacked bar chart section has been added between the existing projection line plot and the component breakdown table.

**What it shows:**
All tide gauge locations are displayed on the x-axis. For each location, the four SSPs (SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5) are stacked vertically, with SSP1-2.6 at the bottom and SSP5-8.5 at the top. This gives an immediate visual comparison of how projected sea-level rise varies both across locations and across emissions scenarios at a single point in time.

**Why it was added:**
The line plot in v1.0 is designed for exploring a single location's full projection timeline across workflows and components. It answers "how does sea level evolve at this station?" The stacked bar chart answers a different question: "across all stations, how much does the choice of emissions scenario matter at year X?" By showing all locations side-by-side with SSPs stacked, it surfaces the spatial spread and scenario spread simultaneously — something not visible in the line plot.

**Controls (same as the line plot):**
- Workflow selector (wf1e–wf4)
- Component selector (total, AIS, GrIS, glaciers, sterodynamics, landwaterstorage, vlm)
- Scale toggle (global / local RSL)
- Year slider (2020–2100, or 2300 for wf*f/wf4)

**Hover tooltip:**
Hovering over any bar shows the location name, tide gauge ID, latitude/longitude, and the individual (non-cumulative) sea-level value for each SSP at that location.

## Sample dashboard

| File | Download |
|------|----------|
| `facts_dashboard_v1.1.html` | [v1.1.0 release](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.0) |

## How to view
1. Download the `.html` file from the release link above
2. Open in any browser — no internet or server required
