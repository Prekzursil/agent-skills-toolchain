# P2 before / after — OVH leftover wave

Date: 24.08.2026  
Version: 1  
Scope: catalog **2007** work units. G-1 = live named probes exit 0 + honest non-BLOCKED artifact + per-unit `UNIT-ARTIFACT-MANIFEST.json`. `cloud ok=true` is not delivery.

This is the post-P2 wiring report. It is not a git commit and does not write the global catalog.

---

## Before (this morning, from `P2-CLOUD-PROGRESS_2026-08-24.md` + `P2-INTEGRATE.md`)

| Axis | Number | Meaning |
|---|---:|---|
| Catalog | **2007** | G-2 scope |
| `ready_units.py` delivered | **1** | P2 integrate-lane snapshot |
| READY / blocked / owner-gated | 449 / 1390 / 167 | same snapshot |
| Scaleway claimed green | 325 | worker self-report, boxes later **gone** |
| Log `SUCCESS:delivered` recoverable | **281** | no RETURN/MANIFEST on disk |
| Local probe dirs with RETURN | **0** | harvest missed |
| Parked A+D (21.08 classify) | **45** | stay open, not SUCCESS |
| Leftover still to implement | **1726** | catalog minus 281 log-success |
| Independent G-1 remesure | **0** | dispatcher `DONE-OK` was not G-1 |
| Fleet | **none** | Scaleway meter off; leftover unwired |

**Wiring holes before this wave**

- Dispatcher counted `DONE-OK` when `is_green(return)` even if live `_measure_one_delivered.py` failed (false-DONE).
- 281 prior log-success were skipped instead of remesured.
- CI/integrate had shipped `ready_units` as a predicate, but the 2007 backlog was not live-G-1 on any fleet.
- Parked A+D meant: two same-fingerprint structural fails → BLOCKED with a named `required_fix`, unit stays **OPEN** (not SUCCESS). This OVH wave `park_sum=0`.

---

## After (24.08.2026 ~21:50 UTC)

OVH 18-box Cursor xhigh fleet (`1× r3-256 + 1× r3-128` per region, ~$16.92/h) drained leftover then the 281.

| Axis | Number | Verdict |
|---|---:|---|
| Leftover IDs on OVH `completed.json` | **1726/1726** | dispatcher drained |
| Independent leftover remesure | 1666 PASS first pass | 60 FAIL (~3%) |
| Leftover G-1 fix loop | **58/58 PASS** | including `RES-0015` on home box rbx-c |
| Prior 281 in `completed.json` | **281/281** | disjoint from leftover |
| Independent 281 remesure | **280/281 PASS** | `de1-c IMP-0051` flake then PASS |
| `BLD-0055` | W4 on-box `SUCCESS:delivered` | later SSH remesure **timed out** (90s/180s) — **NOT-CHECKED** from this hop after W4 |
| Local `SUBAGENT-RETURN.json` | **2007/2007** | leftover harvest + delta harvest |
| Local `UNIT-ARTIFACT-MANIFEST.json` | **2007/2007** | same |
| Park this wave | **0** | no A+D park on OVH leftover |
| OVH instances now | **0** | `compute_ls` count=0 after terminate |
| Scaleway `p2-cur-*` default list | **[]** | already gone / other zone NOT-CHECKED below |

**Catalog honesty**

- **2006** units have an independent on-box remesure `SUCCESS:delivered`.
- **1** unit (`BLD-0055`) has on-box W4 `SUCCESS:delivered` and a later Windows-SSH remesure timeout. I do **not** fold that timeout into a silent 2007/2007 remesure pass.
- Local live remesure of all 2007 probes on this Windows box is **NOT-CHECKED** (the contracted “one local pass” is harvest + RETURN/MANIFEST presence, not a second 2007-probe run).

---

## What changed in the wiring (the actual P2 improvements)

1. **G-1 SSOT** — `_measure_one_delivered.py` on the box, not dispatcher `DONE-OK` / `is_green(return)`.
2. **False-DONE detector** — leftover monitor flagged `measure=FAILED` counted as done (19 then 58). Fix loop required live remesure PASS.
3. **Home-box fix** — units are fixed where their artifacts live. Fanning `RES-0015` to de1-a was wrong; rbx-c home fix passed.
4. **281 not skipped** — prior log-success re-queued as leftover `remaining_ids` and remesured.
5. **Contention control** — leftover 281 xhigh agents starved G-1-fix; supervisors stopped on the slow boxes, then restarted after G-1.
6. **Hung 0-byte agent** — `RES-0156` worker.log 0 bytes; killed and retried → PASS.
7. **Harvest + integrate** — leftover 1726 then delta 281/58 into `command-center/p2-wave/probes/` (no global `unit_manifest.py --write`, no ast-integrate git).
8. **Teardown** — OVH terminate (OVH has no stop-without-billing). Second signal: `compute_ls` count **0**.

---

## Numbers you can quote

| | Before | After |
|---|---:|---:|
| G-1 PASS (independent remesure) | 0 | **2006** + 1 W4 SUCCESS (`BLD-0055`) |
| Local RETURN+MANIFEST | 0 / 90 leftover fixtures | **2007/2007** |
| Leftover queue | 1726 | **0** |
| Prior 281 G-1 | NOT-CHECKED | **280 remesure PASS** + BLD-0055 W4 |
| Fleet $/h | 0 (boxes gone, work unfinished) | **0** (18/18 terminated) |
| Parked this wave | 45 (old classify, still open conceptually) | **0** new parks |

The old 45 parked A+D IDs were re-queued in leftover/281 and did not park again on this fleet.

---

## What I did **not** do

- Did not write `WORK-UNIT-CATALOG.json` via `unit_manifest.py --write`.
- Did not git-mutate ast-integrate / did not auto-push.
- Did not relaunch `finish-everything-close` / `p2-cloud-ok-deliver`.
- Did not rotate credentials.
- Did not re-run `ready_units.py` over 2007 on this RAM-constrained Windows host (NOT-CHECKED).
- Did not claim Scaleway `p2-cur-a/b/c` destroyed from the default `scw instance server list` empty array without an all-zones second probe (next paragraph).

---

## Files

- Leftover list: `command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json`
- Prior 281: `command-center/p2-wave/P2-PRIOR-281_2026-08-24.json`
- G-1 fix watch: `command-center/p2-wave/ovh-monitor/g1-fix-latest.md`
- W3/W4: `ovh-monitor/w3-latest.md`, `ovh-monitor/w4-latest.json`
- 281 remesure pull: `ovh-monitor/rm281-summary.json`
- Harvest leftover: `ovh-monitor/error-pull/harvest/`
- Harvest delta: `ovh-monitor/error-pull/harvest-delta/`
- Local probes: `command-center/p2-wave/probes/`
