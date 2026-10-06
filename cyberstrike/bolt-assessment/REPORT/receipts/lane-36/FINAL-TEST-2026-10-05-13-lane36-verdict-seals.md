# RECEIPT 13 — LANE-36 VERDICT SEALS: ZERO-VALIDATION (d) + AWS-CROSSPAIR=[] FINAL (e)
FINAL-TEST 2026-10-05 · subtask-148 execution B · strictly offline · zero wire calls · sha8-only

## (d) ZERO-VALIDATION SEAL — 0 of ≤10 bounded proxy validations consumed
Rationale chain (each link evidence-backed, receipts 10-12):
1. Deep RE surfaced NO previously-unknown Bolt-domain service key. Exhaustive sweep: 130 catalog entries (22 sha8s) + 2 Mixpanel tokens (F15) across both staged corpora (jadx + apktool trees + strings + splits).
2. MQTT: rider/driver credentials are runtime-provisioned (client: JWT + device UUID; driver: AccessTokenManager short-lived token; broker URL via GetMqttBrokerUseCase) — no static Bolt MQTT secret exists in either binary.
3. driver.applog.bolt.eu: no key material anywhere near the sole anchor (b.java:31); HTTP(S)-only BuildConfig constant; consumer unresolved → nothing to validate.
4. Mixpanel tokens (sha8 e6c777a0 BuildConfig MIXPANEL_TOKEN, 696d9c16) are third-party vendor keys → catalog/report-only per engagement rules, never validated.
5. Google/Maps/Crash keys (3 sha8s) already SSOT-covered byte-identical since 2026-09-17 — validation would burn prior material, explicitly prohibited.
6. github_pat all FALSE; braze_neveruse_matches=[]; no live Bolt-owned credential exists in the corpus.
BOUND: nothing qualified → 0/10 consumed → ZERO-VALIDATION-DOCUMENTED verdict stands for lane-36 execution B. Proxy credential NEVER used this phase (zero egress; vault 0600, credential-line sha8 unchanged from baseline, untouched).

## (e) AWS CROSS-PAIRING SEAL — aws_crosspair=[] FINAL for lane-36; 0 of ≤5 STS calls consumed
Rationale:
1. Stage-A 6-corpora sweep (strings_{client,driver}, jadx both, apktool both): ZERO AWS-20-char key-ID shapes in either app binary.
2. Deep-RE confirmation: no AWS SDK classes, no SigV4 signing paths, no credential-provider chains in either tree.
3. Intersection with lane-34 union corpus (sts_verdicts.tsv, 186 key IDs → 147 DEAD / 39 KEYID-EXISTS): catalog24 ∩ sts186 = 0 (receipt 12 §2.iii) → no corpus key-ID pairs with any mobile-surfaced secret.
4. No STS GetCallerIdentity call placed; no corpus key touched; do-not-burn set {94cd0fc8, 5771ae40, 6a1e88d1, 8aa2d085, 81976adb} untouched.
VERDICT: aws_crosspair=[] FINAL for lane-36 (mobile corpora contribute nothing to the lane-34 AWS matrix; the 39 KEYID-EXISTS remain lane-34's remediation item).

## Attestations
Zero Bolt-estate network; zero DNS; zero STS; zero secret validation; NEVER-ROTATE intact; proxy credential line sha8 (baseline value, not restated) confined to 0600 vault, never printed; sha8-only; zero PII; register untouched (286 ×3 / 98859339…).
