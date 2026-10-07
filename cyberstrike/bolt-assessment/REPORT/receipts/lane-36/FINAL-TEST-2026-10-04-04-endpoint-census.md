# FINAL-TEST-2026-10-04-04 — LANE-36 STAGE A — ENDPOINT CENSUS & DIFF (subtask 132)

- Round: FINAL-TEST (directive 2026-10-04). Subtask: 132. Mode: OFFLINE, catalog-only.
- Script: /work/lane36/lane36_census.py (persisted, v1.0.0). Artifacts: analysis/endpoint_census.md, analysis_raw_client.tsv (158 lines, sha8 a981fc60), analysis_raw_driver.tsv (368 lines, sha8 2f813063), analysis_summary.json.
- Sources swept: jadx java trees (client 35,452 files / 26.67 s; driver 64,451 files / 91.65 s), apktool res/values strings, assets/, network configs, strings dumps of inner APKs. Stripped-URL userinfo count: **0** (no embedded credentials in URLs).

## A. Raw inventory

- Client: 151 distinct URLs (195 occurrences) + 6 distinct bare hosts (7 occ).
- Driver: 354 distinct URLs (899 occurrences) + 13 distinct bare hosts (38 occ).
- Normalized rows: 272; distinct endpoints after noise-drop: **330** → bolt/taxify/boltint/boltsvc ESTATE 160, braze/firebase 17, third-party 153.

## B. Estate classification (vs lane-31 refs)

- **NEW = 39, KNOWN = 6, CHANGED = 115.**
- 13 NEW estate hosts: admin-panel.bolt.eu, admin-panel.prelive.bolt.eu, driver.applog.bolt.eu, driver.live.boltsvc.net, images.bolt.eu, partnerdriver.live.boltsvc.net, partners.bolt.eu, partners.prelive.bolt.eu, prelive.bolt.eu, s.bolt.eu, s.prelive.bolt.eu, scooters.taxify.eu, signup.bolt.eu.
- Notable NEW paths: admin-panel[.prelive].bolt.eu `/fleet/drivers/edit/%s`, `/identity/consumers/rider/%s/overview`, `/ride-hailing-order/orders/order/%s/%s` (client+driver, jadx sources/eu/bolt/servicedesk/report/mapper/a.java) — admin-plane deep references shipped in BOTH mobile binaries; prelive plane rides edge 172.65.223.108 (lane-31). driver.live.boltsvc.net 83 occurrences in driver build config.
- CHANGED bulk: bolt.eu apex locale-path family (https://bolt.eu/auth etc., 40 rows) and www.bolt.eu marketing paths — host known, paths/scheme new vs lane-31.
- KNOWN: rider-broker.ws.bolt.eu, driver-broker.ws.bolt.eu, node.bolt.eu (root paths, lane-31-observed).

## C. 25-endpoint auth map — REFERENCE-MISSING disposition

- The 25-endpoint device-token auth map is **host-side only**: LANE-REGISTER.md line 32 records delivery at `D:\bolt\enum\pulls\device-tokens\` — not present in this container (searched /work, /work/lane31, /work/bolt/REPORT, receipts). Classification therefore performed against lane-31 refs (ATTACK-SURFACE-INVENTORY.md, DELTA-TABLE.md, DNS census 119 hosts).
- SSOT §2 mobile-plane overlay (completed at subtask-132 consolidation, supersedes the "0-hit" disposition note in the 2026-10-05 census receipt):

| SSOT §2 endpoint | census rows | in client | in driver | disposition |
|---|---|---|---|---|
| node.bolt.eu | 5 | yes (BuildConfig) | yes (b.java; network/client/a.java) | KNOWN |
| rider-broker.ws.bolt.eu | 2 | yes (BuildConfig) | yes (eu/bolt/verification/a.java) | KNOWN |
| driver-broker.ws.bolt.eu | 2 | yes | yes (b.java) | KNOWN |
| user.live.boltsvc.net | 3 | yes (BuildConfig.java) | yes (eu/bolt/verification/a.java) | KNOWN (host) — was listed 0-hit in census receipt note; overlay corrects: present in both binaries |
| driver.live.boltsvc.net | 1 | yes | yes (83 occ) | NEW estate host (lane-31 DNS blind) |
| partnerdriver.live.boltsvc.net | 1 | yes | yes (10 occ) | NEW estate host |
| api.iam.bolt.eu | 1 (ref-only) | **no** | **no** | ABSENT from both binaries (raw grep 0) |
| fleet-auth.bolt.eu | 1 (ref-only) | **no** | **no** | ABSENT from both binaries (raw grep 0) |
| admin-panel.bolt.eu (+prelive) | 10 | yes | yes | NEW (SSOT overlay confirms mobile exposure) |
| partners.bolt.eu (+prelive) | 4 | yes | yes | NEW estate host |
| driver.applog.bolt.eu | 2 | yes | yes | NEW estate host |

- Overlay verdict: mobile binaries reference 8/10 auth-plane hosts (2 absent: api.iam.bolt.eu, fleet-auth.bolt.eu — server-side-only surfaces).

## D. Stage-B handoff candidates (no validation performed)

- *.live.boltsvc.net service mesh (driver/user/partnerdriver), admin-panel.{,prelive.}bolt.eu path grammar, partners.{,prelive.}bolt.eu, driver.applog.bolt.eu, boltprelive:// scheme reachability (client).

## E. Attestation

Offline only; no DNS, no HTTP, no TLS. Host literals and endpoint paths permitted per task rules; zero credential values and zero PII in artifacts; URL userinfo stripped count 0 (gate clean).
