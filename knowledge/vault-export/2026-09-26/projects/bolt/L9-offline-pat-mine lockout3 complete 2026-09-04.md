---
title: L9-offline-pat-mine lockout3 complete 2026-09-04
type: note
permalink: main/projects/bolt/l9-offline-pat-mine-lockout3-complete-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- lockout
- L9
- pat-mine
---

- [fact] Lane L9-offline-pat-mine finished 2026-09-04 offline regex over D:\\bolt jira comments, descr_full, deep-mine TSVs, samples. Artifacts: D:\\bolt\\enum\\pulls\\lockout3\\L9-offline-pat-mine\\receipt.md and census.json plus matches.json (full values on disk only).
- [fact] Hits 14227 / unique 2931. Kind unique: akia 180, asia 59, jwt 2661, bearer_jwt 16, okta_00 15. dapi/ghp/gho/github_pat/ssws = 0 (detector self-test fired on synthetics; github_pat.tsv header-only / deep-mine2 0-byte kept).
- [fact] JWT decode via jwt_g09_v2.py NOW=2026-09-04: LIVE 44 hits, expired 6101, NO_EXP 90, DECODE_ERROR 3279. No warehouse SQL; live PAT unused.
- [decision] Full PAT/JWT values persist only in matches.json for lockout recovery; receipt/census/chat carry path+offset+kind+expiry and counts only.
- relates_to [[Bolt harvest: always persist PII and PAT values]]
