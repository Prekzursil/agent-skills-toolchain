# FINAL-TEST RECEIPT 09 — lane-36 Stage A: Per-App Structure & Attack Surface

- Engagement: Bolt Technology OÜ red-team (operator directive 2026-10-04, verbatim authority on record)
- Round / subtask: FINAL-TEST / subtask-143 (lane-36 mobile RE, stage A, phase 2)
- Date: 2026-10-05
- Register impact: NONE (register close-out is subtask-147)
- OFFLINE ATTESTATION: static analysis only — zero network, zero secret validations, proxy vault untouched, NEVER-ROTATE intact.

## 1. ee.mtakso.client (rider) — CA.225.0 CONFIRMED
- versionName CA.225.0, versionCode 4340; minSdk 24, targetSdk 36; base APK + 4 config splits; shared release cert sha8 a75c6372 (receipt 07).
- Exported components: 5 activities / 7 providers / 5 receivers / 4 services.
- Permissions: 38 total, 10 dangerous (incl. background location, calendar read/write, microphone); signature-level: DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION, VERIFF_STATUS_BROADCAST.
- Deep-link surface: bolt://, taxify://, boltprelive://, https://scooters.taxify.eu, bolt.sng.link (AppsFlyer), fbconnect (Facebook SDK), cct.ee.mtakso.client (Chrome custom tabs).
- FINDINGS: (a) allowBackup attribute ABSENT -> defaults TRUE -> adb-backup extraction risk for app-private storage (token theft on debug-enabled devices); (b) boltprelive:// pre-production scheme SHIPPED IN PRODUCTION build.

## 2. ee.mtakso.driver — DA.147.0 CONFIRMED
- versionName DA.147.0, versionCode 860; minSdk 26, targetSdk 36; base + 4 splits; shared release cert sha8 a75c6372.
- Exported components: 2 activities / 6 providers / 5 receivers / 3 services.
- Permissions: 39 total, 9 dangerous; signature-level: MAPS_RECEIVE.
- Deep links incl. http(s)://* WILDCARD intent-filter, bolt.eu hosts, boltdriverapp://, taxifydriverapp://, boltdriver.sng.link.
- allowBackup = false (good).
- FINDINGS: (a) http(s)://* wildcard intent-filter exposes exported intent surface to ANY web origin (intent-redirection/deep-link abuse candidate); (b) scoped cleartext for m.likumi.lv only (see NSC analysis, receipt 07).

## 3. Attack-surface takeaways (stage-B priorities)
- CLIENT: no TLS pinning + allowBackup-default-TRUE + boltprelive:// prod leak -> interceptable traffic on user-CA devices and debug-device token extraction; the 7 exported providers are the top content-provider probing targets for stage B.
- DRIVER: no TLS pinning + wildcard http(s)://* intent filters + the much larger native-lib surface (206 MB XAPK) -> MITM and intent-redirection testing; storage/token-handling RE prioritized for stage B.
- BOTH: shared RSA-1024 release cert (receipt 07) = single point of failure for update integrity across the entire fleet.

## 4. References
- app_structure_client.md sha256 f92c632eae077438a33af945ddfff8beef3441aa76768786fc42e63ff28ab743
- app_structure_driver.md sha256 2382fdc436ad97dca028d8da939cc53329bb88cb1d2df7f9acf188ea0a79d445
- Manifests: manifest_client.json / manifest_driver.json + xapk_meta_client/manifest.json + xapk_meta_driver/manifest.json (all sealed in baseline 8ed49658f63d5172dd138b8bf5103a70aafeea4c3ab3e38d3f6aa202a466f02d).

## 5. Closing attestations (subtask-143, 2026-10-05)
- Zero network / zero DNS; zero secret validations; sha8-only references; zero PII; zero credential values; zero proxy userinfo; NEVER-ROTATE intact.
- Leak-gate over this receipts dir: PASS.
- LANE-REGISTER.md untouched (byte-identical x3, 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
