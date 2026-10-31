# P2 Scaleway progress — 24.08.2026

Date: 24.08.2026  
Version: 1  
Scope: G-2 full catalog (2007 work units), Grok-4.6 xhigh on 3 Education boxes.

This is an inventory after the boxes disappeared. It is not a G-1 completion claim.

## Cloud right now

**Gone.** `scw instance server list` in fr-par-1, fr-par-2, nl-ams-1, pl-waw-1 returns **0 servers**. No volumes, no snapshots, no reserved IPs. SSH to the old addresses fails. Meter is **off**.

Last live babysit ticks:

| Time (UTC) | Live Grok | Queued | Notes |
|---|---|---|---|
| 20.08 07:42 | 33 | 1615 | catalog fleet start (caps 96/48/48) |
| 20.08 09:04 | **190 / 192** | 1251 | peak |
| 20.08 09:26 | 3 | 1225 | collapsed |
| 20.08 11:14 | 0 | 1228 | supervisors `inactive` |
| 21.08 00:16 | 0 | — | last classify; later pulls `scp: Connection closed` |

The 2007 wave ran about **two hours** at high concurrency, then died. It did **not** drain the catalog.

## What classify last saw (21.08 00:16 UTC)

Pulled into the local tree while boxes still answered. After that, the numbers never moved.

| Bucket | Count | Meaning |
|---|---|---|
| claimed green (`status=DELIVERED`) | **325** | worker/self-report, not independently re-measured here |
| close | 4 | |
| work | 69 | |
| park (A+D) | **45** | stays open, not SUCCESS |
| probe dirs | 443 | |
| harvest union (old 303 set) | 303 | |
| catalog | **2007** | G-2 scope |

325 claimed green ≠ 325 G-1. `registered=true` on the last good home pull (19.08 21:42) was **89** of 278 harvest claims. Catalog-wave returns are **not** on disk now (see below).

## What we still have locally (integrated 24.08)

Cloud disks are gone, so this is the recoverable set:

| Artifact | Count | Path |
|---|---|---|
| Worker logs | 888 | `scw-pull/workers/` + pull trees |
| Unique `SUCCESS:delivered <ID>` in those logs | **281** | `CLOUD-DONE-FROM-LOGS-2026-08-21.json` |
| Local `probes/` dirs still present | **90** | mostly leftover fixtures; **0** `SUBAGENT-RETURN.json`; **0** per-unit manifests |
| Files merged from `scw-pull` probe trees (no `node_modules`) | 10 | already under `probes/` |

`pack_delta` / babysit pulls after ~08:36 on 20.08 did not land new returns. A later `scp: Connection closed` failed while boxes were dying. **The 443-probe snapshot is not fully here.** Integrating “the done units” today means: log-claim inventory + leftover catalog list, not 325 live probe trees.

Claim IDs by prefix (log `SUCCESS:delivered`, n=281): ADV 58, RES 48, TST 39, IMP 33, ARC 32, AUD 32, BLD 12, CNF 8, WFA 8, CC 5, CNL 5, REL 1.

## Where we are left vs 2007

| | Count |
|---|---|
| Catalog | 2007 |
| Log-claim done (skip if re-run) | 281 |
| Last classify claimed green (lost returns) | 325 |
| Parked (must stay open) | 45 |
| **Still to implement for G-2** | **~1682–1726** |

Leftover ID list (catalog minus log-success): `P2-CLOUD-LEFTOVER_2026-08-24.json` (`remaining_if_log_success_skipped=1726`).

If you treat last classify 325 as also done, remaining ≈ `2007 − 325 − 45 park = 1637`, plus the 45 parked still open.

## ETA

**None.** There is no fleet. Peak 190 workers lasted ~20 minutes at cap; then 3 workers; then inactive. A 1680-unit drain at 192 × ~40 min/unit is not a number this run earned.

To finish G-2: bring boxes back (Education still cannot take 64c/512G), restore grok-4.6 xhigh + auth in `/root/.grok`, queue the leftover JSON, skip parked + log-success unless a spot-check fails.

## Constraints still in force

- no global `unit_manifest.py --write`
- no ast-integrate git-mutate / no QAS auto-push
- do not relaunch `p2-cloud-ok-deliver`
- cloud `ok=true` is not delivery
- parked = open, not SUCCESS

## Files written this pass

- `command-center/p2-wave/CLOUD-DONE-FROM-LOGS-2026-08-21.json`
- `command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json`
- `command-center/p2-wave/P2-CLOUD-PROGRESS_2026-08-24.md` (this file)
