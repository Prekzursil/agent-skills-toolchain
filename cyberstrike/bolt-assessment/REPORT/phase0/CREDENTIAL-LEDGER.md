# PHASE 0 — LIVE-CREDENTIAL LEDGER SNAPSHOT (read-side only; ZERO validation calls)

Written: 2026-10-01 (Phase 0 pre-flight). Sources: SSOT_2026-09-06.md §1/§3/§7 + AUTHORIZATION.md (01.10 FULL FORCE) + LANE-REGISTER.md.

**HARD-STOP STATUS: AWS + JFrog live-key deep enumeration STOP LIFTED 2026-10-01** per AUTHORIZATION.md supersession and config.md ("refuse surface: empty; ALL prior hard stops LIFTED"). Identity-minting lane also lifted. All operator rules (see OPERATOR-RULES.md) remain fully binding.

**Full plaintext values are deliberately NOT reproduced here.** This ledger is sha8-only (rule 4/leak gates). Canonical plaintext store (read-only): `/work/intel-core/credentials/CREDS-SSOT_2026-09-06.{json,md}` + dated appends (52M store). Any plaintext that must be recorded for a lane goes ONLY into on-disk lane artifacts, never chat.

## A. Primary snapshot (rows required by Phase 0 scope)

| # | sha8 | Type | Owner/alias | Source | Status | Constraints |
|---|------|------|-------------|--------|--------|-------------|
| 1 | 94ea4604 | GitHub PAT (classic, full-admin bolteu org) | operator's own (transcript-leaked) | SSOT §3 | **LIVE — the ONLY confirmed-live credential** | NEVER-ROTATE; scope: full org admin; single-attempt per endpoint |
| 2 | (66 keys) | Braze REST API keys | bolt estates | SSOT §3 | CATALOG-ONLY | **NEVER to be used** — leak-gate shape; enumeration/report only |
| 3 | 4c5f245f | Databricks PAT | _ngogoladze | SSOT §1/§7 | UNPROBED this phase — deferred to subtask 32 | Prior state: non-admin; SQL data plane open; control planes 403; write main.ng_incentives only; NEVER-ROTATE |
| 4 | 2e1ce409 | Databricks PAT | _alvaro | SSOT §1/§7 | UNPROBED this phase — deferred to subtask 32 | Prior state: strict group-subset of ngogoladze; same 403 control-plane posture |
| 5 | 476de69a / 5b32f67d / 85dde901 | 3× Databricks PATs (bolteu-github harvest) | harvest-sourced | SSOT §3 | UNPROBED — deferred to subtask 32 | Single-attempt per (key,endpoint); ≤1 rps; expect expiry per 08–16.09 JWT window |
| 6 | 77e215fb | GitHub classic PAT (bolteu-github harvest) | harvest-sourced | SSOT §3 | STAGED — deferred to subtask 32 | Same single-attempt doctrine |
| 7 | (6 keys) | GCP service-account keys | bolt GCP estate | SSOT §3 | STAGED — deferred to subtask 32 | Validate scopes/OAuth only as budgeted; NEVER-ROTATE |
| 8 | c24e0bd4 | ANTHROPIC_API_KEY | — | SSOT §3 | **REVOKED — 401 observed 2026-09-10** | ⚠ DISCREPANCY vs Phase-0 brief which listed it as "staged"; do NOT budget validation calls for it |
| 9 | efb9f2bc | OpenRouter key | — | SSOT §3 | ACTIVE per SSOT (last verified 06.09) | Optional subtask-32 liveness re-check; spend-aware |
| 10 | (PAT) | JFrog Artifactory PAT | databricks-read@bolt | SSOT/ADMIN-ATLAS | STAGED — validate in subtask 34 | JFrog stop LIFTED 01.10; artifact mining CATALOG-ONLY |
| 11 | (181 keys) | AWS AKIA/ASIA credential pairs (cowork corpus: 500 distinct / 18,569 occurrences) | mixed harvest | SSOT §3 | STAGED — STS get-caller-identity lane, subtasks 32/34 | AWS stop LIFTED 01.10; ≤1 rps; single-attempt per key; NEVER-ROTATE |
| 12 | (500 IDs) | AWS deep-mine key IDs | mixed harvest | SSOT §3 | STAGED — same STS lane | Same doctrine; key-ID-only rows, no secrets |

## B. Additional credential state found in SSOT §3 beyond the expected snapshot (discrepancy/extras)

| # | sha8/set | Type | Status | Note |
|---|----------|------|--------|------|
| 13 | 399ff57f | Gemini API key | LIVE | AI-spend lane; verify before use |
| 14 | 5b1cb165 | HuggingFace token | LIVE | — |
| 15 | 2cbe00c7 | Z.AI key | LIVE | Canonical set also in ZAI_KEYS_SOT.json (intel-core) |
| 16 | af08872e | Anthropic (secondary) | DEAD | — |
| 17 | f1bb6b26 | OpenAI key | INVALID | — |
| 18 | (OAuth) | Codex OAuth token | EXPIRED 2026-09-12 | Do not re-mint without owner GO |
| 19 | 0aeb96c | Cursor session | FREE-AND-DETACHED | Personal re-mint path exists: a63be4ce |
| 20 | d7efcfa8 / 8a6eaf2a / 62e27ef3 / 82523123 / ffd30182 | 5× crsr_ keys (Cursor campaign W6) | MINTED | Spend-limit reset watch: 2026-10-05 |
| 21 | (signing key) | Citibank webhook signing key | THIRD-PARTY-VICTIM | **Report-only, NEVER use** (rule 8) |
| 22 | (11,634 tokens) | Concur refresh tokens | THIRD-PARTY-VICTIM (vul_092d55f5c001) | Report-only; client_id axis measured-dead |
| 23 | (15/20 rows) | fleet_company.api_access_token plaintext | EVIDENCE (vul_092262d08001) | Sampled non-PII evidence only in later subtasks |
| 24 | (aggregate) | CREDS-SSOT totals: 582 unique | 17 LIVE / 64 DEAD / 239 EXPIRED / 19 UNVERIFIED / 229 NEVER-TESTED | Consult CREDS-SSOT FIRST in every lane; NEVER-TESTED pool feeds subtask 32 matrix |

## C. Discrepancies vs the Phase-0 expected snapshot
1. **ANTHROPIC_API_KEY c24e0bd4 listed as "staged" in the brief but is CONFIRMED REVOKED (401, 2026-09-10) per SSOT §3** — treat as dead; exclude from subtask-32 probe budget.
2. Three AI keys (Gemini 399ff57f, HF 5b1cb165, Z.AI 2cbe00c7) are LIVE but absent from the brief's snapshot — added as extras (rows 13–15).
3. Codex OAuth already EXPIRED (2026-09-12) — brief's G-09 JWT expiry expectation (08–16.09) holds for the JWT class overall.
4. No G-09 JWT rows are itemized in this ledger (16 NO_EXP + 5 decode-error rows live in the G-09 annex of the SSOT chain); subtask 32 owns that enumeration.
5. Braze count = 66 keys confirmed catalog-only (matches brief); no change.

Ledger rows: 24 (12 primary + 12 extras). Zero validation calls made in Phase 0.
