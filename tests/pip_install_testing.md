# FACTS Dashboard — pip Install Testing Guide
**Date:** 2026-06-17
**Feature:** `facts-dashboard` pip-installable CLI package

---

## What This Feature Does

Allows users to install the FACTS dashboard generator as a standard Python package:

```bash
pip install git+https://github.com/facts-workbench/facts.plotting.dashboard.git
```

After install, instead of running:
```bash
python facts_dashboard.py --exp-root /path/to/exp/
```

Users run:
```bash
facts-dashboard --exp-root /path/to/exp/
```

No script download required. Works from any directory.

---

## Test Environment

- **Python:** 3.11
- **pip:** 26.1.2+
- **Install type:** `pip install git+https://github.com/facts-workbench/facts.plotting.dashboard.git`

---

## Manual Test Cases

Run each test case after installing the package into your environment.

---

### T-01 | CLI entrypoint resolves correctly

```bash
facts-dashboard --help
```

**Expected:** Help text prints. Shows all flags (`--exp-root`, `--ssp-dir`, `--output`, etc.).
**Failure:** `command not found: facts-dashboard` or import error.

---

### T-02 | `--exp-root` mode (multi-SSP experiment)

```bash
facts-dashboard \
  --exp-root /path/to/exp.alt.emis/ \
  --output ./pip_exp_alt_emis.html
```

**Expected:** Dashboard generates. Log shows "Loaded N SSPs", location count, "Done."
**Failure:** Exception during generation. File missing or 0 bytes.

---

### T-03 | `--ssp-dir` mode (single SSP folder)

```bash
facts-dashboard \
  --ssp-dir /path/to/exp.alt.emis/coupling.ssp585/ \
  --output ./pip_ssp585_only.html
```

**Expected:** Dashboard generates with that SSP only.
**Failure:** Exception or empty dashboard.

---

### T-04 | `--output` path respected

Check that T-02 and T-03 outputs landed at the specified `--output` path and not in the working directory or package install location.

**Expected:** Files only at the path given to `--output`.
**Failure:** HTML written to wrong location.

---

### T-05 | `--verbose` flag works

```bash
facts-dashboard \
  --exp-root /path/to/exp.alt.emis/ \
  --output ./pip_verbose.html \
  --verbose
```

**Expected:** More detailed log output than T-02 (DEBUG-level lines visible).
**Failure:** Same output as without `--verbose`.

---

### T-06 | `__version__` accessible

```bash
cd /tmp && python -c "import facts_dashboard; print(facts_dashboard.__version__)"
```

**Expected:** Prints the package version string.
**Note:** Run from a neutral directory (e.g. `/tmp`). Running from inside a repo directory that contains `facts_dashboard.py` causes that local file to shadow the installed package, since `''` (CWD) is first in `sys.path` when using `-c`. This is a test environment artifact, not a bug for end users.
**Failure:** `AttributeError: module 'facts_dashboard' has no attribute '__version__'`

---

### T-07 | Dashboard opens and renders correctly in browser

Open the HTML file generated in T-02 in a browser.

**Expected:** Dashboard loads. Line plot, component table, bar chart all visible. No red errors in the browser console.
**Failure:** Blank page. Console TypeErrors. Missing sections.

---

### T-08 | Uninstall is clean

```bash
pip uninstall facts-dashboard -y
facts-dashboard --help
```

**Expected:** After uninstall, `facts-dashboard` command is not found.
**Failure:** Command still works after uninstall (leftover files).

---

### T-09 | Reinstall after uninstall works

```bash
pip install git+https://github.com/facts-workbench/facts.plotting.dashboard.git
facts-dashboard --help
```

**Expected:** Package reinstalls cleanly. CLI works again.
**Failure:** Install error or CLI broken after reinstall.

---

## Sign-Off

| # | Test | Result | Notes |
|---|------|--------|-------|
| T-01 | CLI entrypoint | ✅ PASS | |
| T-02 | `--exp-root` mode | ✅ PASS | |
| T-03 | `--ssp-dir` mode | ✅ PASS | |
| T-04 | `--output` path respected | ✅ PASS | |
| T-05 | `--verbose` flag | ✅ PASS | |
| T-06 | `__version__` accessible | ✅ PASS | Run from `/tmp` to avoid CWD shadowing installed package |
| T-07 | Browser render | ✅ PASS | |
| T-08 | Uninstall clean | ✅ PASS | |
| T-09 | Reinstall works | ✅ PASS | |

**All 9 passed.**
