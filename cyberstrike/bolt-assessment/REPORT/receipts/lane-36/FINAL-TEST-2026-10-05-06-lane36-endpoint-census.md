# FINAL-TEST RECEIPT 06 — lane-36 Stage A: Endpoint / Host Census (mobile corpus diff)

- Engagement: Bolt Technology OÜ red-team (operator directive 2026-10-04, verbatim authority on record)
- Round / subtask: FINAL-TEST / subtask-143 (lane-36 mobile RE, stage A, phase 2)
- Date: 2026-10-05
- Register impact: NONE (register close-out is subtask-147)
- OFFLINE ATTESTATION: zero network, zero secret validations, proxy vault untouched, NEVER-ROTATE intact; all hosts below were enumerated from static corpora only and deliberately NOT probed.

## 1. Inputs (all verified under /work/lane36/analysis/, dir 0700, files 0600)
- analysis_raw_client.tsv — 158 lines (151 distinct URLs + 6 barehosts) — sha256 a981fc6033c218d791d271654477891178f90c537c52c1d0c6241a254fbdf7ea
- analysis_raw_driver.tsv — 368 lines (354 distinct URLs + 13 barehosts) — sha256 2f81306397327a7e0f8c9f3b9269042b326ae9966ce00e75a2c378228a33a44a
- analysis_summary.json — sha256 e1236114dfa3d823612ccb8b0d56627cdbfcfc990343e134c059b84f6cf67183
- Normalized census: endpoint_census.md — sha256 1c80768aec4d47e13a2418a65f996d3a2741f2581de5b58039a2f2103ca9b096
- Companion manifest SHA256SUMS.analysis (8/8 OK) — sha256 9db119af460ec5b4d3506065c71c3f66bbd1ac293e7ed480e1f5ea02fd0d9fe7
- Note: these analysis artifacts were produced AFTER the sealed directory baseline (SHA256SUMS 8ed49658…) by design; they are anchored by SHA256SUMS.analysis instead. Sealed baselines were not modified.

Noise hosts dropped before classification: w3.org, slf4j.org, xml.org, apache.org, github.com raw docs, generic googleapis schemas, ccil.org, mapbox docs. All bolt.eu / taxify.eu / boltint.net / boltsvc.net / braze / firebase entries retained.

## 2. Reference baselines
- lane-31 attack-surface census: FOUND and used — /work/bolt/REPORT/receipts/lane-31/ATTACK-SURFACE-INVENTORY.md and /work/bolt/REPORT/receipts/lane-31/DELTA-TABLE.md (with SHA256SUMS.lane-31 alongside).
- 25-endpoint auth map: NOT FOUND anywhere in the container (searched /work/bolt/REPORT/, /work/lane31*, /work/bolt-intel/, /work/intel-core/, /work/on-demand/) -> recorded as 'reference-missing'; NOT guessed. Retry scheduled for stage B (subtask-144; lane-32/33 bundles).

## 3. Classification totals (272 normalized rows)
- NEW = 39
- CHANGED = 115
- KNOWN = 6
- Per-row source attribution (<=3 files per row), occurrence counts, and app attribution (client/driver/both) are recorded per row in endpoint_census.md (sha256 above).

## 4. Mandatory reconciliation rows (verified by direct grep of trees + strings dumps)
| host | verdict | evidence / app |
|---|---|---|
| rider-broker.ws.bolt.eu | KNOWN | both apps; rider WebSocket broker |
| driver-broker.ws.bolt.eu | KNOWN | driver app; driver WebSocket broker |
| node.bolt.eu | KNOWN | both apps |
| driver.applog.bolt.eu | NEW | client + driver strings; applog ingest host — stage-B cross-reference candidate |
| fleet-auth.bolt.eu | 0 hits in current builds | grep over both trees + both strings dumps: no match |
| api.iam.bolt.eu | 0 hits in current builds | same method: no match |
| tracking.taxify.eu | 0 hits in current builds | same method: no match |
| boltint.net (any subdomain) | 0 hits in current builds | 'boltint' grep across both trees + both dumps: no match |

## 5. Stage-B candidate NEW hosts (recorded ONLY — deliberately NOT probed)
- *.live.boltsvc.net family: driver.live.boltsvc.net, partnerdriver.live.boltsvc.net, user.live.boltsvc.net
- admin-panel.bolt.eu and admin-panel.prelive.bolt.eu
- partners.bolt.eu and partners.prelive.bolt.eu
- driver.applog.bolt.eu (also in section 4)

## 6. Closing attestations (subtask-143, 2026-10-05)
- Zero network / zero DNS / zero host probing; every verdict is static-corpus-derived.
- Zero secret validations; sha8-only references; zero PII; zero credential values; zero proxy userinfo; NEVER-ROTATE intact.
- Leak-gate over this receipts dir: PASS.
- LANE-REGISTER.md untouched (byte-identical x3, 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
