# LANE-34 RECEIPT 02 — EXCLUSION MATRIX + SWEEP SET (FINAL-TEST 2026-10-04, Stage 1 Part B)
Date: 2026-10-04 · Author: lane-34 stage-1 operator · Offline build from sealed artifacts — ZERO network calls.

## Primary sealed sources
/work/lane32/keys-vault/b_sts_sweep_results.json (array[5], rows indexed by keyid_sha8 / secret_sha8 / token_sha8) · lane-32 CRED-MATRIX.md Wave-B table · lane-32 SSOT (verdict_detail KEYID-EXISTS).

## sha8 index mapping (explicit)
- 8aa2d085, 81976adb, 94cd0fc8, 5771ae40 → sha8 of **aws_access_key_id** (sts-temp creds, Databricks job 1076209361132100 job_parameters echo, wave 2026-09-14).
- 6a1e88d1 → sha8 of **aws_secret_access_key** (longlived pair; keyid recorded only as pubshape AKIA…IBBJ; github sagemaker-jenkins / driver-safety-predictor notebooks).
- 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085 → sha8 of **aws_access_key_id** (KEYID-EXISTS: 403 SigV4-missing-secret = identity recognized, never live-usable without secret).

## Dispositioned — DO NOT RE-BURN (no STS call)
DEAD: 94cd0fc8 · 5771ae40 · 6a1e88d1 — EXPIRED: 8aa2d085 · 81976adb.
Raw sealed JSON (authoritative): DEAD = 81976adb, 94cd0fc8, 6a1e88d1; EXPIRED = 8aa2d085, 5771ae40. CRED-MATRIX Wave-B table (mirrored by directive) transposes 81976adb↔5771ae40; both are do-not-burn either way — sweep set unaffected.

## Reconciliation — "5 dead + 2 expired"
NOT supported by sealed evidence. Sealed = **3 DEAD + 2 EXPIRED = 5 dispositioned AWS credentials total** (exactly the 5 sha8s the directive enumerates). No additional prior-round DEAD AWS sha8s exist in any sealed artifact; CRED-MATRIX histogram DEAD=8 includes 5 non-AWS tokens (databricks 476de69a / 85dde901 / 5b32f67d, github 77e215fb, gcp-SA a9759f95) outside lane-34 scope. Discrepancy recorded per directive; no scope impact.

## Corpus cross-check
- Dispositioned sha8s present in the 186-key corpus union: **NONE (0/5)** — prior dispositions derive from Databricks job-param echoes + github notebook sources, disjoint from these corpora.
- PRIORITY KEYID-EXISTS sha8s present in corpus union: **ALL 6** → ordered FIRST.

## FINAL UNEXCLUDED SWEEP SET
**Size = 186 distinct key-ID sha8s = exactly 186 STS calls in the follow-up sweep** (1 per (keyid, sts.amazonaws.com), no retries, ≥1.2 s pacing ⇒ ≥224 s minimum).
Order: 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085 (PRIORITY), then remaining 180 in ascending sha8 order. Full ordered list (values): /work/lane34/sweep_set.json (0600); sha8-only list: /work/lane34/sweep_set.sha8list.txt (0600).

## Sweep semantics note for follow-up call
0 complete pairs (no aws_secret_access_key in corpora) ⇒ every call is a **keyid-existence probe**, not a SigV4-signed get-caller-identity. Expected verdict classes per lane-32 SSOT: INVALIDCLIENTTOKENID (dead/absent) vs KEYID-EXISTS (recognized identity). No LIVE-identity enumeration (≤15 budget) can fire unless secret material is later staged; S3 census (≤10) likewise gated on a LIVE identity.

## Binding rules honored
NEVER-ROTATE · no key creation · no console/UI attempts · no destructive actions · no phishing/MFA interception · third-party-victim credentials report-only (rule 8) · ≤1 rps / ≥1.2 s pacing · single attempt per (key, endpoint) · sha8-only fingerprints in all receipts · zero PII values.
