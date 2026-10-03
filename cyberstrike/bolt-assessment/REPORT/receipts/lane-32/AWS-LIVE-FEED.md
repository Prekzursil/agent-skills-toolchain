# AWS-LIVE-FEED — lane 32 Wave B → subtask 57 (lane 34 AWS/JFrog deep enum)
Sweep window: 2026-10-01T20:0xZ (in-container, single-attempt per key, retries max_attempts=0, 1.1s pacing).

## LIVE SigV4-able identities: NONE (0/5)
- 2 EXPIRED (ExpiredToken): sts-temp keyid sha8 8aa2d085, 81976adb
- 3 DEAD (InvalidClientTokenId): sts-temp keyid sha8 94cd0fc8, 5771ae40; long-lived secret sha8 6a1e88d1
- Prior host-side verdicts (2026-09-14) matched in 5/5 cases — no drift.

## Task-premise reconciliation (IMPORTANT for subtask 57)
- Task premise: "181 AKIA/ASIA pairs WITH secrets". Mounted corpus holds **5 pairs total** (4 sts-temp triples from
  Databricks main.ng_databricks.job_run_timeline job-param echo, job 1076209361132100, Dec-2025 sessions; 1 long-lived
  pair AKIA pubshape:AKIA…BJBJ secret sha8 6a1e88d1 from bolteu_data-science sagemaker-jenkins notebook).
- The 181-pair cowork archive (500 distinct IDs / 18,569 occurrences, Jira INFRAPCI-79 old→new rotation pairs) lives
  host-side at D:\bolt\enum\pulls\cowork-inv\secrets_found.json — NOT mounted. Secrets exist there; key-IDs only here.

## Secret-less catalog (SigV4 impossible — catalog-only, zero network attempts)
- Union: **234 unique key IDs** (AKIA 186 / ASIA 48). Sources: CREDS-SSOT main 188 (143 NOT-TESTABLE-BY-RULE, 39 DEAD,
  6 KEYID-EXISTS); deep-mine__aws_key.tsv 213 unique of 500 rows (177 overlap w/ SSOT; presigned-URL X-Amz-Credential
  extractions from Jira, dates 2020–2025); jira-tail append 10 new untested; bypass-append 1 (already in SSOT).
- 6 KEYID-EXISTS rows (sha8 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085): GetCallerIdentity recognized
  the key-ID pre-2026-09-06 — identity exists, secret never found. **Subtask-57 action: recover paired secrets from
  host-side cowork-inv archive; then single-attempt STS + iam simulate-principal per identity.**
- Long-lived pair account guess 287845475429 (taxify/bolt datascience, from notebook bucket name inference) —
  UNCONFIRMED; key now DEAD (InvalidClientTokenId) — treat account guess as stale.

## Handoff notes
- JFrog/Concur lanes unaffected. WATCH7 (testregistry.bolt.eu) stays DNS-only per LANE-REGISTER.
- No third-party-victim accounts resolved (no key produced a foreign ARN) — report-only rule not triggered this wave.
