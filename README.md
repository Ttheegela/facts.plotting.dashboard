# facts.plotting.dashboard

Generates a self-contained interactive HTML dashboard from [FACTS](https://github.com/radical-collaboration/facts) sea-level projection outputs.

No FACTS installation needed. Output is a single `.html` file — open in any browser.

---

## Requirements

- [Docker](https://docs.docker.com/desktop/) ≥ 20
- FACTS `.nc` output files from a completed run

---

## Usage

### 1. Clone

```bash
git clone https://github.com/Ttheegela/facts.plotting.dashboard.git
cd facts.plotting.dashboard
```

### 2. Build

```bash
bash docker/build.sh
```

Run once. Rebuild only after updating `facts_dashboard.py`.

### 3. Generate

```bash
bash docker/run.sh --exp-root /path/to/experiment/
```

The dashboard is saved as `dashboard.html` next to your data. Open it in any browser.

---

## Input structure

```
experiment/
├── coupling.ssp126/
│   ├── location.lst       ← tide gauge names (optional)
│   └── output/
│       ├── coupling.ssp126.total.workflow.wf1e.local.nc
│       └── ...
├── coupling.ssp245/
├── coupling.ssp370/
└── coupling.ssp585/
```

The dashboard auto-detects all scenarios, workflows, components, and locations. Non-standard scenario names (e.g. `rco.LL.nz`) are supported. Partial runs are fine — missing files are skipped.

---

## Other input modes

**Scenarios in separate folders:**
```bash
bash docker/run.sh --ssp-dir /path/to/ssp126/ --ssp-dir /path/to/ssp585/
```

**Single NetCDF file:**
```bash
bash docker/run.sh --single-nc-file /path/to/total.workflow.wf1e.local.nc
```

**AR6-style confidence files:**
```bash
bash docker/run.sh \
  --confidence-root /path/to/4_confidence_level_files/ \
  --confidence-level medium_confidence
```

**Custom output path and title:**
```bash
bash docker/run.sh \
  --exp-root /path/to/experiment/ \
  --output   /path/to/dashboard.html \
  --title    "My FACTS Run"
```

---

## All flags

| Flag | Description |
|------|-------------|
| `--exp-root PATH` | Root folder containing scenario subdirectories |
| `--ssp-dir PATH` | One scenario folder — repeat for multiple |
| `--single-nc-file FILE` | Single total sea-level `.nc` file |
| `--confidence-root DIR` | Root of AR6-style confidence level files |
| `--confidence-level LEVEL` | `medium_confidence` or `low_confidence` (default: `medium_confidence`) |
| `--location-lst FILE` | `location.lst` for tide gauge names — auto-detected if not provided |
| `--output FILE` | Output HTML path (default: next to input data) |
| `--title TEXT` | Dashboard title (auto-generated if omitted) |

---

## Troubleshooting

**`ERROR: facts-viz image not found`** → Run `bash docker/build.sh` first.

**`ERROR: Docker is not installed or not in PATH`** → Install and start Docker Desktop.

**`ERROR: No scenario directories found`** → `--exp-root` must point to the folder *containing* the scenario subfolders, not inside one.

**Location names show as IDs** → Add `location.lst` to the scenario folder, or use `--location-lst /path/to/location.lst`.

**Data only goes to 2100** → Only `wf*e` workflows found. Run `wf*f` or `wf4` in FACTS for projections to 2300.
