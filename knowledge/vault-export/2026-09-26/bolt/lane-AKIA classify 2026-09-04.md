---
title: lane-AKIA classify 2026-09-04
type: note
permalink: main/bolt/lane-akia-classify-2026-09-04
status: active
valid_as_of: '2026-09-04'
---

- [decision] LANE-AKIA lockout classification: CLASSIFIED-ONLY no pairing. Do not call STS/IAM with unpaired presign access-key IDs.
- [fact] Unique AKIA=180 ASIA=59 (L9 census, L9 matches.json, and union store agree). L9 hits akia=4310 asia=378 also agree with hits.tsv kind column.
- [fact] Pairing probes all zero: TSV rows, secret_kv (7 rows, empty assignments only), 4688 ±2KiB windows on 117 source files. GetCallerIdentity attempts=0.
- [fact] TSV aws_key files have no secret_access_key column. s2of4_aws_key.tsv is 0-byte (kept). TSV unique ASIA=47; extra 12 ASIA are jira descr_full only.
- [fact] Same-TSV-row Bolt account IDs on 7 unique AKIA / 0 ASIA (451613234044 n=3, 737418964414 n=3, 287845475429 n=1). Window proximity is 70 unique — not same-row.
- [fact] Detector both-states PASS for AKIAIOSFODNN7EXAMPLE and ASIA prefix; docs example absent from deep-mine/aws_key.tsv.
- relates_to [[LOCKOUT-HARVEST-10LANE]]
- relates_to [[PLAN-AND-AWS-STATE]]
See also [[SECRETS-LEDGER]].

Report: D:\\bolt\\analysis\\lane-AKIA-classify_2026-09-04_v2.md (v1 stub preserved). Redacted index: D:\\bolt\\enum\\pulls\\lockout3\\parent\\akia\\index_redacted_v2.json