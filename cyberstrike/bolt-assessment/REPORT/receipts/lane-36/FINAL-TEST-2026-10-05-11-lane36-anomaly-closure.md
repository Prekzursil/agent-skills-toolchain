# RECEIPT 11 — LANE-36 ANOMALY CLOSURE (auth-map / braze / xapk_meta / applog / dead-code webview)
FINAL-TEST 2026-10-05 · subtask-148 execution B · strictly offline · read-only over sealed artifacts · sha8-only

## A. 25-endpoint auth map → REFERENCE-MISSING-FINAL
- Archivist verdict: the map NEVER existed inside the container. Operator-side only: D:\bolt\enum\pulls\device-tokens\ (register line 32, device-token replay lane, closed 2026-09-20; produced task-4-era). No sha8 recorded; content never receipted.
- Register line 32 (sole provenance, verbatim relevant fragment): "25-endpoint auth map delivered (D:\bolt\enum\pulls\device-tokens\) for future use".
- Fallback references: lane-31 ATTACK-SURFACE-INVENTORY.md + DELTA-TABLE.md.
- Replacement: F18 recovered static auth-map set (lane36_final_inventory.md §A.4): @POST /driver/{getAccessToken, startAuthentication, sendMagicLink, v2/getLoginConfiguration, authenticateWithMagicLink, authenticate, resendVerificationCode, completeAuthentication}; @GET /driver/getAuthenticationConfiguration; /driver-auth/partnerDriver/*; @POST /driver/getDriverPortalMagicToken.
- Disposition: CLOSED — reference-missing-FINAL; no further search attempts scheduled.

## B. braze_neveruse count drift (72 vs 73 vs 66) → RECONCILED (authoritative)
- Sealed file /work/lane36/braze_neveruse_sha8.txt: 75 lines = 3 comment/header lines + 72 key-lines; 72 unique keys (no duplicates).
- AUTHORITATIVE verdict split of the 72: LIVE 66 / DEAD 4 / NOT-A-CREDENTIAL 2.
- Header self-declaration "68 live / 3 dead / 2 not-a-cred = 73" is WRONG: 68+3+2=73 exceeds the 72 keys on disk; the 73rd entry DOES NOT EXIST (recount ×2, byte-level).
- Historical live-count 66 vs file-total 72: counting artifact — the 2026-09-17 census counted LIVE only; dead/not-a-cred keys were present but uncounted. Zero new keys, zero reclassifications since 2026-09-17.
- Kuzu /work/lane37/graphdb (provider=braze, read-only) corroborates the 72-key set.
- Sealed file header left UNTOUCHED by design (hash stability); correction recorded in register wording (receipt 14 §3.vi) only.
- Intersection re-confirmation: 22-catalog sha8s ∩ 72-key set = ∅ (braze_neveruse_matches=[] stands).

## C. F17 xapk_meta "missing" → FALSE ANOMALY (closed)
- /work/lane36/xapk_meta_client/ and /work/lane36/xapk_meta_driver/ EXIST (mtime 2026-10-05T01:01Z; manifest.json 2,914 B / 4,326 B).
- Manifest-covered: SHA256SUMS (sha256 8ed49658…) entries 20/21 = xapk_meta_client/manifest.json 9a5296d0…, xapk_meta_driver/manifest.json 4bc98130…; both verify OK.
- TREE-FINGERPRINTS.txt agg hashes recompute EXACT match: xapk_meta_client 3b7985e0…, xapk_meta_driver 019da872….
- Root cause of the "missing" report: path-lookup error (wrong working directory during the post-crash resume); NOT staging drift; no downstream dependency (native payload carried by splits/, provenance sealed receipt-05).
- Disposition: CLOSED — false anomaly; register wording notes it (receipt 14 §3.vii); nothing to rebuild.

## D. driver.applog.bolt.eu consumer → UNRESOLVED (A2, document-only)
- Sole anchors: BuildConfig URL + ee/mtakso/driver/b.java:31 (occ 2 in driver strings). No SDK class, auth-header shape, payload category, or batching policy recoverable from staged corpora.
- Verdict: INFO (F10); stage-B candidate left UNPROBED by operator rule (no live probing of NEW hosts this subtask).

## E. VerificationWebView universal file access → DEAD-CODE CANDIDATE (A3)
- Driver g.java:64-65 setAllowFileAccessFromFileURLs(true) + setAllowUniversalAccessFromFileURLs(true): HIGH-if-reachable.
- No instantiation site found across jadx_driver 64,465 files → treated as dead code in DA.147.0.
- Standing instruction: re-check on the next driver build ≥ DA.148; if reachable, re-rate HIGH.

## Attestations
Zero network/DNS; zero validation; zero STS; read-only over sealed artifacts (braze_neveruse_sha8.txt byte-identical post-check); sha8-only; zero PII; register untouched.
