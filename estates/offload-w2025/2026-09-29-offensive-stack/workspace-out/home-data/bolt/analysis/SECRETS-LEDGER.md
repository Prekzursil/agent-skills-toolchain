---
title: SECRETS-LEDGER
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/home-data/bolt/analysis/secrets-ledger
---

# Secrets ledger — verified counts as of 2026-09-03 (misty-moon)
Basis: deep-mine v1 (reconciled) + usefulness audit + jwt_triage_v2 + CSRF cluster analysis. STRICT quarantine: **zero secrets validated by use** — all figures are evidence-grade counts.

| Class | Lines | Unique/real | Status |
|---|---:|---:|---|
| Atlassian JWTs | 1,144 | 1,067 unique | 5 LIVE (exp 08–16.09.2026): MVRT-2215, PAWT-128, TAXP-4393, LSS-72037, LSS-64291 · 1,044 expired · 13 NO_EXP · 5 undecodable (kept, reasons logged) |
| password KV | 529 | ~148 real-looking | unvalidated; placeholders/env-refs/prose = ~72% |
| AWS | 500 | 0 secret keys | presigned X-Amz-Credential key-ids (identifiers); 1 pasted key deactivated |
| conn_url (TiDB et al.) | 214 | 214 | infra-map value; embedded creds mixed |
| cookies | 264 | 84 live-per-session Box csrfToken | HR/HS workflow still active at corpus end (2026-08-26); see CSRF-TOKEN-CLUSTER.md |
| Azure SAS | 51 (v2: 5) | 5–51 | v1/v2 count anomaly open under remine2 reconciliation |
| basic-auth | 153 | 3 user:pass | 150 prose slop |
| Google API keys | 14 | 14 | unvalidated |
| Slack | 6 xox + 4 hooks | 10 | unvalidated |
| PEM blocks | 2 | 2 | unvalidated |
| secret KV | 8 | 8 | unvalidated |
| OpenAI | 15 | **0** | RETRACTED — sk-sro filename false-positives |
| bearer | 2 | **0** | template placeholder + expired 2023 ya29 |
| Anthropic | 0 | **0** | CLOSED 2026-09-04 — dedicated sk-ant-/KV scan, 446 files, zero hits (ai_key_audit.py) |
| Cursor | 0 | **0** | CLOSED 2026-09-04 — token/env/api2.cursor.sh/header patterns, 446 files, zero hits |

**Totals: ~2,991 evidence lines · ~250–450 plausibly-real · 0 validated by use (by policy).**
**AI-provider class (OpenAI/Anthropic/Cursor): ZERO usable or real keys exist anywhere in the corpus — formally closed 2026-09-04.**
Growth vector (legitimate): delta-sync of new comments/issues — the leak sources were still active at corpus end.