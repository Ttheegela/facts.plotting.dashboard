# v1.1.4 — Location Dropdown, Line-Plot Improvements, Bar Chart Controls

**Script:** [`facts_dashboard_v1.1.4.py`](./facts_dashboard_v1.1.4.py)

---

## What is new in v1.1.4

### 1. Location selection dropdown (bar chart)

The locations displayed in the grouped bar chart are now controlled by a **toggle-button dropdown**, consistent with all other controls on the dashboard (workflow, component, scale, year, quantile).

**Before:** All 24 tide gauge locations were always shown, creating a crowded chart with no way to focus on a subset.

**After:** A "Locations ▼ (all 24)" toggle button sits in the controls row. Clicking it opens a checklist panel listing every location in the dataset (name + tide gauge ID). Tick any combination to compare those stations side by side. The button label updates live to reflect how many are selected (e.g. "Locations ▲ (3 / 24)"). Closing the panel collapses it cleanly.

**Why this matters:** The primary purpose of the bar chart is to compare RSL projections across multiple stations simultaneously. With 24 locations always visible, the chart is too dense to read. The dropdown lets users focus on the specific stations they care about — e.g. Karachi vs. Mumbai vs. Colombo — without losing access to the full dataset.

**Implementation approach:**

Bokeh's `Toggle` widget controls the `visible` property of a `CheckboxGroup` — both are native Bokeh models, so no HTML/CSS tricks are needed. Two `CustomJS` callbacks are wired:
- `Toggle.js_on_change("active", ...)` — shows/hides the panel and updates the button arrow and count
- `CheckboxGroup.js_on_change("active", ...)` (label-update only) — updates the button count while the panel is open, so the count stays accurate without the user needing to close and reopen the dropdown

The bar chart callback (`JS_BAR`) already reads `chk_loc.active` (the checked indices) to determine which locations to include. No changes to the data logic were needed — only the UI layer.

**Technical issues encountered:**

- *Approach 1 — Custom HTML dropdown via `Div.text` + `<script>`*: Browsers do not execute `<script>` tags injected via `innerHTML`. The click handler never fired.
- *Approach 2 — `TextInput` + `MultiSelect`*: `MultiSelect` requires Ctrl+click for multi-selection (non-intuitive for users). Abandoned in favour of explicit checkboxes.
- *Approach 3 — CSS `position:absolute` dropdown panel*: Bokeh layout containers use `overflow:hidden`, which clips any absolutely-positioned child element. The dropdown was invisible once inside the layout.
- *Final approach — Bokeh `Toggle` + `CheckboxGroup.visible`*: Pure Bokeh, no CSS tricks. Reliable across all browsers.

---

### 2. Line plot y-axis fixed at 0

The line plot y-axis minimum is now always fixed at 0 mm so that projections across different SSPs, workflows, and locations are visually comparable on the same scale.

**Before:** The y-axis autoscaled to the current data range, making screenshots misleading when comparing runs (the same physical value could appear at different heights in different views).

**After:** `y_init_min = 0.0` regardless of data. The max is still data-driven (padded, capped at `YMAX_FIXED`). The Y-range slider still lets users zoom in if needed.

---

### 3. Global line quantile selector

A new **"Line quantile" dropdown** lets the user choose which percentile the solid line (and component table) displays: Median (p50), 5th, 17th, 83rd, or 95th.

**Before:** The line always showed the median (p50). The shaded bands showed p17–p83 and p5–p95, but the line itself was fixed.

**After:** The user can switch the line to any of the five standard FACTS quantiles. The `JS_UPDATE` callback reads `q_line_sel.value` and uses it as the key into `data_dict` entries.

---

### 4. Bar chart SSP checkbox selector

A `CheckboxGroup` was added to the bar chart section allowing the user to show or hide individual SSP scenarios. Bars repack dynamically — widths and x-positions recalculate so the group spacing stays consistent regardless of how many SSPs are active.

---

### 5. Bar chart Y-axis range slider

A `RangeSlider` was added below the bar chart controls, consistent with the line plot. Users can zoom into a specific mm range without affecting the line plot slider.

---

### 6. X-axis label fix (KARACHI always shown — resolved)

**Bug:** After the user changed the location selection via the bar chart checkbox, the x-axis labels did not update — every position showed "Karachi" regardless of which locations were actually displayed.

**Root cause:** The original implementation used `p_bar.xaxis.major_label_overrides` — a Python dict assigned from JavaScript. In Bokeh's model system, reassigning a property from CustomJS does not trigger a reactive re-render; the plot simply ignores the update.

**Fix:** Replaced `major_label_overrides` with a `CustomJSTickFormatter` backed by a `ColumnDataSource` (`label_cds`). The formatter reads location names from `label_cds.data` at render time. When the user changes the location selection, JS_BAR updates `label_cds.data` and calls `label_cds.change.emit()` — a proper reactive signal that triggers a redraw. Labels now always match the current selection.

A secondary issue: floating-point x-positions (e.g. `0.55`, `1.1`) were used as group centers. When converted to strings as dict keys in JavaScript, floating-point imprecision caused key mismatches. Fixed by using integer group centers (`list(range(n_locs))`), with bars offset symmetrically within each group. Integer keys are always exact.

---

## Sample dashboard

| File | Download |
|------|----------|
| `facts_dashboard_v1.1.4.html` | [v1.1.4 release](https://github.com/tt633/facts.plotting.dashboard/releases/tag/v1.1.4) |

## How to view
1. Download the `.html` file from the release link above
2. Open in any browser — no internet or server required
