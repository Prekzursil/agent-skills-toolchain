# P2 harness before / after — 24.08.2026

Date: 24.08.2026  
Version: 1  
What this is: harness and wiring diffs after doing (1) local BLD-0055 remesure, (2) stratified live harvest proof, (3) catalog/manifest wiring. Not a git commit.

---

## 1. BLD-0055 (the last cloud hole)

| | Before this pass | After |
|---|---|---|
| Independent remesure from Windows SSH | timeout 90s/180s | n/a (boxes gone) |
| Local `_measure_one_delivered.py` | not run | **SUCCESS:delivered** (WSL) |
| Probe 1 / probe 2 | unknown locally | both exit 0 |
| Fail that had to be fixed first | `No module named 'fan_in'` | `tools/fan_in/barrier.py:admit` now exists |
| Manifest | sha of 25768-byte receipt | live sha `30973be2…` / 49862 bytes of `receipts/BLD-0055.json` |

Windows cmd cannot run the Unix probe prefix `PYTHONDONTWRITEBYTECODE=1 python3 -B …` (`'PYTHONDONTWRITEBYTECODE' is not recognized`). Local G-1 for this unit is **WSL Linux python3**.

---

## 2. Harvest proof (stratified live remesure)

86 IDs: BLD-0055 + WFA-0001 + the 58 leftover G-1-fix IDs + 2 per prefix from leftover/281.

| | Count |
|---|---:|
| Sample n | 86 |
| **SUCCESS:delivered** | **1** (`BLD-0055`) |
| FAIL | 85 |

Fail classes (local tree, not cloud):

| Class | Meaning |
|---|---|
| `predicate:absent` | catalog `output_path` file is missing locally (vast majority) |
| `sentinel-absent` | file exists, catalog sentinel not in body (`WFA-0001`, some ADV) |
| `self-declared:BLOCKED` | file exists, `state` is BLOCKED (`AUD-0082`, `CC-0011`, `BLD-0001/0002`, `REL-0001`, `BLD-0041`) |

**Load-bearing finding:** leftover harvest tarballs packed `probes/` only (`tar … -C p2-wave probes`). They did **not** pack `command-center/receipts/`. Extract has **zero** `receipts/` trees. Local `receipts/*.json` = **132** files. Cloud G-1 passed because those receipts lived on the OVH box. That byte stream is gone with terminate. Probe RETURN+MANIFEST **2007/2007** locally is not the G-1 artifact.

So (2) did what it was for: it proved the harvest, and the harvest is **probe-complete, receipt-incomplete**.

---

## 3. Catalog / `ready_units` / condition-11 wiring

### `ready_units.py` (delivery predicate)

| | Before this pass | After |
|---|---:|---:|
| units | 2007 | 2007 |
| **delivered** | **241** | **241** (unchanged) |
| READY | 298 | 298 |
| blocked | 1302 | 1302 |
| owner-gated | 166 | 166 |
| present but NOT delivered | 81 | 81 |

`delivered()` reads the catalog `output_path` (existence + parse + not BLOCKED + contract). Writing the global unit manifest does **not** move this number. Without harvested receipts, leftover 1726 cannot become delivered here.

Morning `P2-CLOUD-PROGRESS` said delivered **1**. That was pre-harvest. **241** is already the post-harvest local predicate (earlier P2 receipts on disk), not 2007.

### `unit_manifest.py --write` (condition 11)

| | Result |
|---|---|
| Stock `--write` | **FAILED** fail-closed: `receipts/BLD-0010.json` names absent `probe1-environment-smoke.raw.txt` |
| Missing named artifacts before restore | 562 |
| Restored from harvest/siblings | 37 |
| Still missing | 523 |
| Complete-only writer | **191 entries from 185 complete receipts; skipped 89 incomplete** |
| File | `command-center/UNIT-ARTIFACT-MANIFEST.json` (was **not** in git HEAD; newly written) |

Stock `--write` staying red is **correct**. Forcing it green would have been the same Goodhart as dispatcher `DONE-OK`.

---

## Harness changes (what actually moved)

1. **G-1 SSOT** — `_measure_one_delivered.py`: live probes + per-unit manifest sha + non-BLOCKED artifact. Cloud `ok=true` is ignored.
2. **False-DONE retired** — leftover dispatcher `is_green(return) OR measure` is why 58 units were “done” while remesure failed.
3. **`tools/fan_in/barrier.py`** — cited by BLD-0055 (`admit` is digest-match, fail-closed on absent). Also mirrored at `command-center/tools/fan_in/` because harvested probes set `REPO = Path.parents[3]` (command-center, not repo root).
4. **Local remesure rail** — WSL + `PYTHONPATH=repo:tools:tools/command-center`. Windows cmd is not a G-1 host for these probes.
5. **Condition-11** — stock writer fail-closes; complete-only writer registers only receipts whose named files exist.
6. **Harvest contract hole** — next cloud pack must include `command-center/receipts/` (and other catalog `output_path`s), not only `probes/`.

---

## What I did **not** do

- Did not run stock `unit_manifest.py --write` until it lied green.
- Did not invent 523 missing raw files.
- Did not git-commit.
- Did not claim `ready_units` delivered=2007.
- Did not claim local G-1 of leftover 1726.

Honest remaining work if you want local G-1 of the leftover set: recover `output_path` artifacts (they are not on this disk; OVH is terminated) or re-emit them from probe trees **only where a probe actually wrote the receipt**.
