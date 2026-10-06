# LANE-34 RECEIPT 01 — CORPUS PARSE (FINAL-TEST 2026-10-04, Stage 1 Part A+D)
Date: 2026-10-04 · Author: lane-34 stage-1 operator · Offline analysis only — ZERO network calls in this receipt.

## Corpora verified (sha256 vs lane-53 inventory receipt 01)
| corpus | bytes | sha256 | expected | result |
|---|---|---|---|---|
| /work/on-demand/drive-staging/wave-2026-09-14/cowork-inv/secrets_found.json | 340,202 | 2966783c47e55f068eb5e6fdebe698b03edb0d9f187f3ff076864827567d59e9 | 2966783c… | MATCH |
| /work/on-demand/drive-staging/wave-2026-09-14/bolteu-github-inv/secrets_found.json | 38,836 | b44ca784382916a2942ca3610992c4a58339b84137ae27a58a03a1250a394f70 | b44ca784… | MATCH |

## Per-class distinct counts
cowork-inv (500 entries): jwt 249 · aws_access_key 181 · generic_kv 32 · google_api_key 11 · databricks_pat 10 · anthropic_key 5 · github_token 4 · slack_token 3 · openai_key 3 · private_key 2.
bolteu-github-inv (46 findings): google_api_key 32 · aws_access_key_id 6 · anthropic_api_key 3 · databricks_pat 3 · github_pat_classic 1 · private_key_block 1.
Cowork metadata occurrences_by_type: aws 15,337 · jwt 2,169 · generic_kv 508 · databricks 277 · google 117 · slack 73 · openai 38 · private_key 26 · github 18 · anthropic 6.
sha8-field integrity: cowork 500/500 match sha256(value)[:8]; github 45/46 match — sole mismatch is private_key_block whose .sha8 field is the sentinel string "marker" (not an AWS class; report-only).

## AWS pair extraction (Part A)
- Entries carrying an AWS access key ID: cowork 181 + github 6 = 187 entries, all AKIA-prefixed 20-char (0 ASIA).
- Entries carrying BOTH aws_access_key_id AND aws_secret_access_key: **0 / 187**. Context and generic_kv classes were exhaustively censused for secret markers (aws_secret / SecretAccessKey / wJv / 40-char secret-shapes): no AWS secret material exists in either corpus. generic_kv (32) holds miscellaneous passwords/tokens (Jira/admin-panel snippets, DB docs, placeholders) — non-AWS, report-only.
- **Complete pairs: 0. Key-ID-only entries: 187.** Consequence: the follow-up STS sweep cannot SigV4-sign; it executes 1 keyid-existence probe per distinct key ID (lane-32 KEYID-EXISTS methodology) at fixed endpoint sts.amazonaws.com.

## Cross-corpus dedupe (keyed on sha8 of aws_access_key_id)
cowork distinct 181 · github distinct 6 · overlap 1 (sha8 9bca2f24 — identical value verified across both corpora) · **union distinct key IDs = 186**.
Note: prior-round lane-32 seal referenced the archive as the "181-pair cowork archive"; on-mount reality is 181 key-ID-only entries. Union of total distinct entries across all classes remains 546 (500 + 46 − 0 entry-level overlap).

## Part D — non-AWS classes catalog (REPORT-ONLY per standing rule 8)
ZERO validation attempts of any kind against any non-AWS secret class. Catalog counts as above; full credential values remain only in 0600 working files under /work/lane34/ (pairs.json, class_counts.json) — never in receipts.

## Artifacts (0600)
/work/lane34/pairs.json · /work/lane34/class_counts.json · /work/lane34/sweep_set.json · /work/lane34/sweep_set.sha8list.txt · /work/lane34/parse_corpora.py (0700) · /work/lane34/exclusion_matrix.md (see receipt 02).
