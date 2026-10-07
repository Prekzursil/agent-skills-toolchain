# FINAL-TEST-2026-10-04-02 — LANE-36 STAGE A — STRUCTURE INVENTORY (subtask 132)

- Round: FINAL-TEST (directive 2026-10-04). Subtask: 132. Mode: OFFLINE, catalog-only.
- Sources: apktool 2.7.0 decoded manifests (at_client/at_driver), AndroidManifest.xml, jadx 1.5.6 trees, apksigner/keytool equivalents (apksigner absent — openssl/JADX cert parsing used; deviation documented in receipt -01 of 2026-10-05 series).

## A. Rider client — ee.mtakso.client (CA.225.0, versionCode 4340)

- minSdk 24 / targetSdk 36; base + 4 config splits (arm64_v8a, armeabi_v7a, mdpi, xxhdpi).
- Exported components: 5 activities / 4 services / 5 receivers / 7 providers.
- Permissions: 38 requested (10 dangerous-class); 2 app-defined custom permissions.
- Deep links / autoVerifies: bolt://, taxify://, **boltprelive://** (prelive scheme in production build — flagged F6), scooters.taxify.eu, bolt.sng.link, fbconnect, cct.ee.mtakso.client.
- allowBackup flag ABSENT from manifest → platform default TRUE (weak backup exposure; client backup_rules weak — F1 pairing).
- Notable exported: CrossAppLoginService — EXPORTED, permission-less, guarded by a signature-permission allowlist internally (MEDIUM, F2); all 7 providers exported (7/7), incl. FileProvider surfaces.
- Application class + init flow enumerated in app_structure_client.md (analysis/).

## B. Driver app — ee.mtakso.driver (DA.147.0, versionCode 860)

- minSdk 26 / targetSdk 36; base + 4 config splits (arm64_v8a, armeabi_v7a, mdpi, xxhdpi).
- Exported components: 2 activities / 3 services / 5 receivers / 6 providers (providers 6/6 exported).
- Permissions: 39 requested (9 dangerous-class); 2 app-defined custom permissions.
- Deep links: boltdriverapp://, taxifydriverapp://, boltdriver.sng.link (autoVerify), bolt.eu, fbconnect.
- allowBackup=false (GOOD).
- Root/tamper: RootUtils present as dead code (F11); no Play Integrity/attestation on critical flows.

## C. Signing posture (public-cert fingerprints; full SHA-256 of release cert permitted)

- Both apps: v2 + v3 schemes (sig-block magics verified: v2 0x7109871a; v3 0xf05368c0 / 0x6dff800d / 0x2146444e; "Brew" stamp 0x42726577); **no v4**.
- Release signer (identical in BOTH apps): self-signed, O=Mtakso OU, **RSA-1024 (WEAK key)**, validity 2013→2038, sha8 **a75c6372** (full SHA-256 in analysis/cert_keystore_report.md; sha8-only here). Single shared release key across client+driver = update-integrity single point of failure.
- cert0 (both apps, byte-identical, NOT the release signer): CN=Android, O=Google Inc., RSA-4096, 2020-05-19→2050-05-19, sha8 **3257d599**, SHA-256 32:57:D5:99:A4:9D:2C:96:1A:47:1C:A9:84:3F:59:D3:41:A4:05:88:45:83:FC:08:7D:F4:23:7B:73:3B:BD:6D (PEM sha8 13917b39) — Google Play Frosting stamp, public material.
- Split PKCS#7 blocks sha8s: 56d65335 / a03ea2ca / 1cabdacd / a4dafe89.

## D. Keystore / embedded-cert inventory

- Zero *.p12/*.bks/*.jks/*.pfx/*.crt/*.cer in either tree; no google-services.json secrets beyond cataloged public API keys (receipt -03).
- Only PEM material in trees: cert0 public-cert extractions (ours) + netty SslUtils PUBLIC probing cert/key constants (receipt -03, class FALSE).

## E. Network security config & pinning posture

- NSC: driver-only (`res/xml/network_security_config.xml`): cleartext permitted SOLELY for m.likumi.lv; trust anchors = system only; **no pin-sets**.
- Client: NO network_security_config → platform defaults (cleartext off on target 28+ but no explicit hardening).
- Grep across jadx trees: **zero** CertificatePinner / custom sslSocketFactory / custom X509TrustManager / permissive HostnameVerifier usage → **ZERO TLS PINNING in both apps** (HIGH, F7; certificate-substitution MITM feasible on attacker-controlled networks — pairs with proxy egress evidence from lane-34).

## F. Cross-references

- Details: analysis/app_structure_client.md, app_structure_driver.md, analysis/cert_keystore_report.md; receipts FINAL-TEST-2026-10-05-07 (certs/pinning), -09 (structure), -10 (deep-RE verdicts).

## G. Attestation

Offline only. No component was invoked; no APK was executed; no network performed. sha8-only fingerprints; zero PII; public-cert full digests permitted per task rules.
