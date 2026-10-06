# RECEIPT 10 — LANE-36 DEEP-RE VERDICTS (auth / storage / root / webview / native)
FINAL-TEST 2026-10-05 · subtask-148 execution B · strictly offline (zero network, zero app execution, zero validation) · sha8-only · zero PII

Corpora (hash-stable, baseline 8ed49658…): jadx_client 35,452 files agg 14cf7324… / jadx_driver 64,465 agg 1b540eef… / at_client 4,220 agg 8f8a432b… / at_driver 4,936 agg 3c6c6293… / splits agg 87b9bae7…
Accepted deviations: client jadx log truncated ~44%; driver 588 decode errors; PEMs named *_cert0.der.pem.

## 1. AUTH (document-only; OTP/MFA never interacted with)

### 1a. MQTT credential provisioning — brokers rider-/driver-broker.ws.bolt.eu
CLIENT (CA.225.0):
- MqttUserInfoRepository — W1() username = authenticator.n() + "." + X1(); X1() = persistent UUID.randomUUID() persisted in PLAIN SharedPreferences key "mqtt_uuid" (device-stable identifier).
- Y1() password = user JWT via jwtTokenRepository (TokenRepository.kt, classes13.dex) — short-lived session token, no static secret.
DRIVER (DA.147.0):
- CONNECT built in eu/bolt/driver/mqtt/hivemq/a.java (~line 933): simpleAuth with EMPTY username + AccessTokenManager secret as password.
- Broker URL endpoint-provisioned at runtime via GetMqttBrokerUseCase (…/auth/step/u.java); RetryPolicy maxRetryTimeInSeconds=30.
- AccessTokenManager (service/token/c.java): AtomicReference + Mutex async refresh; AccessToken @Serializable {accessToken, expiry:Long} → SHORT-LIVED, no static MQTT secret.
Verdict CLIENT: LOW (F9 — device-persistent UUID in plain prefs + JWT password; identifier disclosure only). Verdict DRIVER: LOW (F8 — empty username + short-lived token; broker URL endpoint-provisioned).

### 1b. NEW driver.applog.bolt.eu ingestion
- TLS confirmed: sole occurrence strings_driver.txt:446482 (https scheme).
- Consumer class/auth-header/payload/batching: UNRESOLVED in staged corpora (sole anchor ee/mtakso/driver/b.java:31 + BuildConfig URL; pairs node.bolt.eu /app-log, register L98/L116).
Verdict: INFO (F10, document-only; STAGE-B CANDIDATE — NOT PROBED this engagement).

## 2. TOKEN / KEY STORAGE
CLIENT: HIGH (F1). AuthPreferenceController.java:54-58 — plain CoroutinesPreferenceWrapper Scope.DEVICE, zero crypto for active JWT + username. allowBackup=TRUE; backup_rules.xml + data_extraction_rules.xml exclude ONLY androidx-security-crypto prefs + eu.bolt.deviceid.settings.xml → auth prefs INCLUDED in adb-backup/device-transfer exfil. Chains: boltprelive:// surface + shared RSA-1024 cert sha8 a75c6372.
DRIVER: GOOD (F12). Real EncryptedSharedPreferences (core/storage/crypto/b.java; AndroidX MasterKey AES256_GCM; h.java:132); allowBackup=FALSE; short-lived tokens.

## 3. ROOT / DEBUG / TAMPER
BOTH APPS: MEDIUM (F11) — NO ENFORCED ATTESTATION.
- Driver RootUtils (utils/m0.java): test-keys + 9 su-path probes + `which su` — ZERO external callers → dead code.
- No Play Integrity / SafetyNet / RootBeer / magisk / frida / xposed / debugger gates in either app.
- Client eu/bolt/client/crossapplogin/d.java SignatureValidator: constant-time MessageDigest.isEqual SHA-256 allowlist (DI-injected) — cosmetic-grade tamper posture overall.

## 4. WEBVIEW / DEEP-LINK
CLIENT:
- WebChallengeRibView.java:61 — JS enabled for captcha only; no addJavascriptInterface anywhere.
- boltprelive:// pre-prod scheme LIVE in prod (at_client manifest:114-121; DeeplinkActivity :100 exported singleTask noHistory; AttributionDeeplinkActivity :139; SplashHomeActivity alias :90) — MEDIUM (F6).
- CrossAppLoginService EXPORTED + permission-less (action ee.mtakso.client.action.BIND_AUTH_TOKEN_SERVICE) serving getAuthToken=G2()/getUsername=H2(); binder enforces per-transaction calling-UID signature allowlist → MEDIUM residual (F2; DI-injected allowlist source unresolvable).
DRIVER:
- PlainWebView.kt:187-189 — JS + DOM storage + file access, NO URL allowlist; SSL errors fail-closed (tracker-only) → MEDIUM (F4).
- VerificationWebView (g.java:64-65) setAllowFileAccessFromFileURLs(true) + setAllowUniversalAccessFromFileURLs(true) — HIGH-IF-REACHABLE (F3); no instantiation site in staged corpora → dead-code candidate; retest on later builds.
- Stage-A "wildcard http(s)://*" RETRACTED (F5): AndroidManifest:2-62 is a <queries> block; real filters = boltdriverapp://, taxifydriverapp://, boltdriver.sng.link (autoVerify), bolt.eu http+https, fbconnect cct.ee.mtakso.driver.

## 5. NATIVE LAYER (26 libs: arm64-v8a 11 client-split / armeabi-v7a 15 driver-split; 26 distinct sha8s; base APKs zero .so)
- Full 26-row sha8 inventory: lane36_final_inventory.md §D (sealed in SHA256SUMS.analysis 9/9).
- Pinning indicators (SSL_CTX_set_verify / X509_verify_cert / spki-digest): 0 hits across all 26 libs → NATIVE PINNING: NO.
- Combined with stage A (no Java pinning) → ZERO TLS PINNING ANYWHERE in either app — HIGH (F7); user-CA MITM viable fleet-wide; chains with F1.
- New native endpoints: 0. Bolt-owned native code: none (third-party SDK surface only).

## 6. VERSION → CVE (report-only)
- driver OkHttp 5.0.0 — exact, no matching CVE in local knowledge (CVE-2021-0341 fixed in 4.9.2).
- client OkHttp — version stripped → MATCH-DEFERRED.
- netty (full driver stack) — version stripped → MATCH-DEFERRED (candidates CVE-2021-21295/21290/37136/37137, CVE-2023-34462).
- okio — version stripped → MATCH-DEFERRED (note CVE-2023-3635 <3.4.0).
- OpenSSL/BoringSSL — NOT bundled; conscrypt strings are OkHttp platform probes.
- Final ranges: [CVE-RANGES PENDING RESEARCH] placeholder in register wording (receipt 14 §3.ix).

## Attestations
Zero network/DNS; zero secret validation; zero STS; sha8-only; zero PII; zero credential values; NEVER-ROTATE intact; register untouched (286 lines ×3, sha256 98859339…); streaming analysis, no full-tree copies; /tmp scratch pruned.
