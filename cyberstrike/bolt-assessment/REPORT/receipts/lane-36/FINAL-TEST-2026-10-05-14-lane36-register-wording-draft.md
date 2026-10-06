# RECEIPT 14 — LANE-36 FINAL INVENTORY POINTER + PROPOSED REGISTER WORDING (DRAFT — NO APPEND)
FINAL-TEST 2026-10-05 · subtask-148 execution B · strictly offline · sha8-only · zero PII

## 1. Final inventory pointer
/work/lane36/analysis/lane36_final_inventory.md — sha256 d7c0f76f953905b0ffd83bf00a9bb352ec2502695936c43f3bdf461be46168b4 (sha8 d7c0f76f), 11,057 B, mode 0600, sealed as entry 9/9 of /work/lane36/analysis/SHA256SUMS.analysis (old entries 1-8 untouched).
Contents: §A endpoint inventory (13 NEW estate hosts, 39 NEW rows = 4+4+3+3+1+1+1+1+17+1+1+1+1; BuildConfig corroboration user/driver/partnerDriver.live.boltsvc.net + node.bolt.eu + rider/driver-broker.ws.bolt.eu; control hosts 0-hit; F18 static auth-map set) · §B key inventory (130 entries / 22 sha8s + F15 Mixpanel 2; family verdicts) · §C cert inventory (release cert sha8 a75c6372 RSA-1024 O=Mtakso OÜ 2013-06-25→2038-06-19 shared; cert0 Google Frosting sha8 3257d599; zero keystores; no pinning; driver-only NSC cleartext m.likimi.lv) · §D native inventory (26 libs, 26 distinct sha8s, third-party only) · §E verdict seals · §F anomaly dispositions · §G disk guard.

## 2. Status of this block
DRAFT ONLY — physical append deferred to subtask-151 close-out (identical append ×3 with hash proof). Register remains 286 lines / sha256 98859339… until then. No register file modified by this subtask.

## 3. PROPOSED REGISTER WORDING BLOCK (lane-36 execution B, FINAL-TEST)

### 3.i vul_l36_b1 [HIGH][client ee.mtakso.client CA.225.0] Backup token extraction chain
Rider auth material (active JWT + username) persisted in PLAIN SharedPreferences (AuthPreferenceController.java:54-58) while allowBackup=TRUE and backup_rules.xml/data_extraction_rules.xml exclude only androidx-security-crypto prefs + eu.bolt.deviceid.settings.xml → auth prefs recoverable via adb backup / device transfer on any device holding an unlocked backup. Chains with vul_l36_b6 (boltprelive://) and the shared RSA-1024 release cert (a75c6372). Remediation: exclude auth prefs from backups or migrate to EncryptedSharedPreferences (driver already compliant — F12 pattern).

### 3.ii vul_l36_b2 [HIGH][both apps] Zero TLS pinning (Java + native)
No certificate pinning in either app: OkHttp client stack unpinned (stage A) AND zero pinning indicators across all 26 native libs (receipt 10 §5) → user-installed-CA MITM of all rider/driver traffic viable fleet-wide, enabling credential/token interception over the unpinned MQTT-WS and REST planes. Chains with F1. Remediation: implement OkHttp CertificatePinner + NSC pin set; document pin-rotation strategy.

### 3.iii Medium/low entries
- vul_l36_b3 [MEDIUM][client] Exported permission-less CrossAppLoginService (ee.mtakso.client.action.BIND_AUTH_TOKEN_SERVICE) serving getAuthToken/getUsername; mitigated by per-transaction constant-time SHA-256 caller-signature allowlist (DI-injected allowlist source unresolvable statically) — residual: any component on a compromised build chain could qualify. (F2)
- vul_l36_b4 [HIGH-IF-REACHABLE][driver] VerificationWebView file+universal access TRUE (g.java:64-65); no instantiation site in DA.147.0 → dead-code candidate; retest ≥ DA.148. (F3)
- vul_l36_b5 [MEDIUM][driver] PlainWebView.kt:187-189 JS+DOM+file access with NO URL allowlist; SSL errors fail-closed (tracker-only). (F4)
- vul_l36_b6 [MEDIUM][client] boltprelive:// pre-prod scheme live in prod on exported DeeplinkActivity (singleTask noHistory) — pre-prod handler surface in production attack surface. (F6)
- vul_l36_b7 [MEDIUM][both] Root/tamper detection dead code (driver RootUtils m0.java zero callers); no Play Integrity/Frida/Xposed/debugger gates → runtime instrumentation unimpeded. (F11)
- vul_l36_b8/b9 [LOW][driver/client] MQTT credential patterns: empty-username + short-lived token password (driver); device-persistent UUID username in plain prefs + JWT password (client). (F8/F9)

### 3.iv Retraction note (supersedes stage-A receipt-09 wording)
RETRACTED: driver "wildcard http(s)://* intent-filter" — the AndroidManifest:2-62 block is a <queries> element, NOT an intent-filter. Actual driver filters: boltdriverapp://, taxifydriverapp://, boltdriver.sng.link (autoVerify), bolt.eu (http+https), fbconnect cct.ee.mtakso.driver. Receipt-09 wording stands corrected by this entry; no register row was ever appended for the wildcard claim (no baseline change).

### 3.v Auth-map disposition note
Reference-missing-FINAL: the 25-endpoint auth map (register line 32, device-token replay lane, closed 2026-09-20) was NEVER present inside the container — operator-side D:\bolt\enum\pulls\device-tokens\ only; no sha8 recorded; content never receipted. Fallback: lane-31 ATTACK-SURFACE-INVENTORY.md + DELTA-TABLE.md. Replacement static auth-map set (F18): @POST /driver/{getAccessToken, startAuthentication, sendMagicLink, v2/getLoginConfiguration, authenticateWithMagicLink, authenticate, resendVerificationCode, completeAuthentication}; @GET /driver/getAuthenticationConfiguration; /driver-auth/partnerDriver/*; @POST /driver/getDriverPortalMagicToken.

### 3.vi braze_neveruse authoritative correction (sealed file header left untouched)
/work/lane36/braze_neveruse_sha8.txt authoritative count: 72 keys = 66 LIVE / 4 DEAD / 2 NOT-A-CREDENTIAL. File header's "68 live / 3 dead / 2 not-a-cred (=73)" is WRONG; the 73rd entry does not exist. Historical "66" was a live-only count, not a smaller set; zero growth/reclassification since 2026-09-17. braze_neveruse_matches=[] re-confirmed (catalog22 ∩ 72 = ∅). File intentionally NOT modified (hash stability); this note is the authoritative correction of record.

### 3.vii Staging anomaly closure note (F17)
xapk_meta_client/xapk_meta_driver reported "missing" post-crash was a FALSE ANOMALY (path-lookup error): both directories exist, manifest-covered (SHA256SUMS entries 20/21) and TREE-FINGERPRINTS-exact (3b7985e0… / 019da872…). No staging drift; nothing rebuilt.

### 3.viii NEW-host register rows (genuinely-new surfaces; all UNPROBED — documented only)
- intel_l36_h1 admin-panel.bolt.eu + admin-panel.prelive.bolt.eu [HIGH-INTEREST]: rider/driver identity + order admin paths (/fleet/drivers/edit/%s, /identity/consumers/rider/%s/overview, /ride-hailing-order/orders/order/%s/%s) — credential-gated admin surface, adjacent lane-31 admin.bolt.eu mTLS interstitial; prelive edge 172.65.223.108. DO NOT probe without operator staging.
- intel_l36_h2 partners.bolt.eu + partners.prelive.bolt.eu [MED-INTEREST]: partner-portal plane (SSOT-append 2026-09-17 battery family).
- intel_l36_h3 signup.bolt.eu [LOW-INTEREST]: signup static (SSOT-append family).
- intel_l36_h4 prelive.bolt.eu + s.bolt.eu + s.prelive.bolt.eu [LOW-INTEREST]: plane labels (assetlinks.json on prelive root).
- intel_l36_h5 images.bolt.eu [LOW-INTEREST]: asset CDN (17 rows).
- intel_l36_h6 scooters.taxify.eu [LOW-INTEREST]: DeeplinkValidator allowlist host.
- intel_l36_h7 driver.live.boltsvc.net + partnerdriver.live.boltsvc.net [MED-INTEREST]: BuildConfig primary-API family extension (user.live L121 known).
- intel_l36_h8 driver.applog.bolt.eu [STAGE-B CANDIDATE]: app-log ingestion, family covered L116 (node.bolt.eu /app-log, CSP report-only beehive); consumer unresolved; NOT PROBED.

### 3.ix CVE report-only note (versions from staged binaries)
driver OkHttp 5.0.0 (no matching CVE; CVE-2021-0341 fixed 4.9.2) · client OkHttp version-stripped MATCH-DEFERRED · netty version-stripped MATCH-DEFERRED (candidates CVE-2021-21295/21290/37136/37137, CVE-2023-34462) · okio version-stripped MATCH-DEFERRED (note CVE-2023-3635 <3.4.0) · OpenSSL/BoringSSL not bundled (conscrypt strings are OkHttp platform probes).
[CVE-RANGES PENDING RESEARCH] — to be filled from parallel research before subtask-151 append.

### 3.x Mixpanel catalog gap (F15)
Two mixpanel_token-family entries uncataloged: sha8 e6c777a0 (BuildConfig MIXPANEL_TOKEN) + 696d9c16. ACTION at sealing: extend secret-triage catalog family set; report-only (third-party vendor keys).

## 4. Handoff notes
- subtask-149 (lane-55 JWT triage from jwt_triage_v2.tsv, 1,145 lines, sha8 b9bcb15c): 12-row G-09 gap closure; NO-RE-BURN datahub JWT sha8 f5cc101f + Databricks PATs 4c5f245f/2e1ce409; ≤10 bounded LIVE-CANDIDATE validations via proxy ONLY if warranted; receipts under lane-55/.
- subtask-150 (evaluation checkpoint): consume 3.ix CVE placeholder fill; counted severity tally over the ACTUAL append content (this draft + prior FINAL-TEST entries); compact lane-34 ZERO-LIVE closure note; Zendesk DNS-only recheck due (sha8 1420af19; ≤2 DNS queries, zero HTTP); Cursor report-only; ACM renew before 2027-01-08.
- subtask-151 (close-out): physically append this block ×3 byte-identical; re-verify 286+Δ baseline ×3; add remediation rows for 39 exposed AWS key IDs (lane-34) + mobile exposures (F1/F7 top mobile actions); refresh REPORT-INDEX/OPERATOR-ACTIONS (PAT 4c5f245f remains TOP ACTION); full leak-gate battery; FINAL-TEST-CLOSED attestation with complete proxy-egress accounting (this phase: ZERO egress).

## Attestations
Zero network/DNS; zero validation; zero STS; register NOT appended (286 ×3 / 98859339… intact); sha8-only; zero PII; zero credential values; proxy vault untouched.
