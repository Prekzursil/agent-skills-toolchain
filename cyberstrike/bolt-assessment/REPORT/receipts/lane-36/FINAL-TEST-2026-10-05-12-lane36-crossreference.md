# RECEIPT 12 — LANE-36 CROSS-REFERENCE (39 NEW census hosts vs register; key sets vs SSOT/braze/sts)
FINAL-TEST 2026-10-05 · subtask-148 execution B · strictly offline · single register source: /work/bolt/REPORT/LANE-REGISTER.md (286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17, ×3 byte-identical) · sha8-only

## 1. Host cross-reference table (census authority endpoint_census.md sha256 1c80768a…)

| Host (13 NEW estate) | Rows | Register prior coverage | Classification |
|---|---|---|---|
| admin-panel.bolt.eu | 4 | none (lane-31 adjacency: admin.bolt.eu mTLS interstitial; admin-panel.taxify.eu NXDOMAIN) | GENUINELY-NEW |
| admin-panel.prelive.bolt.eu | 4 | plane L19/L57/L109-111 (menu-food.prelive health 200; edge 172.65.223.108) | GENUINELY-NEW (plane-known) |
| partners.bolt.eu | 3 | none (lane-31 DNS census: partner.bolt.eu/partner.taxify.eu singular only) | GENUINELY-NEW |
| partners.prelive.bolt.eu | 3 | none in register; SSOT-append 2026-09-17 battery | GENUINELY-NEW (SSOT-APPEND-REF) |
| signup.bolt.eu | 1 | none in register; SSOT-append battery | GENUINELY-NEW (SSOT-APPEND-REF) |
| prelive.bolt.eu | 1 | plane L57 (Spectrum *.bolt.eu edge); /.well-known/assetlinks.json new | GENUINELY-NEW label |
| s.bolt.eu | 1 | none | GENUINELY-NEW |
| s.prelive.bolt.eu | 1 | none | GENUINELY-NEW |
| images.bolt.eu | 17 | none | GENUINELY-NEW (asset CDN, read-only) |
| scooters.taxify.eu | 1 | zone L56/L108/L117 (pki/upload variants); host new; DeeplinkValidator allowlist both apps | GENUINELY-NEW label (zone-known) |
| driver.applog.bolt.eu | 1 | L116 (CSP report-only disclosed applog.bolt.eu beehive-bolt-eu + beehive-csp + S3); node.bolt.eu /app-log L98; SSOT-append battery | REGISTER-COVERED family / NEW label; STAGE-B CANDIDATE NOT PROBED |
| driver.live.boltsvc.net | 1 | family: user.live L121; host new; BuildConfig | GENUINELY-NEW label |
| partnerdriver.live.boltsvc.net | 1 | family: user.live L121; host new; BuildConfig | GENUINELY-NEW label |

Register-covered families explicitly reconciled: rider-/driver-broker.ws.bolt.eu → L103 (lane-35 MQTT-WS fail-silent) + L240 (lane-47 retest); node.bolt.eu → L98/L121; *.live.boltsvc.net → L121 (user.live) with driver/partnerDriver labels NEW; admin-panel(.prelive)/partners(.prelive) → GENUINELY-NEW; signup.bolt.eu → GENUINELY-NEW (SSOT-REF); prelive.bolt.eu → GENUINELY-NEW label on covered plane; driver.applog.bolt.eu → family covered L116; scooters.taxify.eu → GENUINELY-NEW label; firebaseio + iamcache.braze → third-party (non-estate) rows in census, NOT register material (braze scope handled SSOT-side).
Controls (0 census NEW hits, verified): fleet-auth.bolt.eu L103/L121 · api.iam.bolt.eu L101/L173 · boltint.net L118/L257-258 · tracking.taxify.eu NOT-PRESENT (0 register, 0 census).
NET RESULT: 13 NEW estate hosts → 12 GENUINELY-NEW (of which 8 wholly-new labels) + 1 family-covered NEW label (driver.applog); register wording required for all 13 (receipt 14 §3.viii).

## 2. Key cross-reference (catalog authority secret_triage.md sha256 9998548a…; 130 entries / 22 sha8s; +2 Mixpanel F15 → probe set 24)

(i) probe24 ∩ CREDS-SSOT_2026-09-17_newhosts-auth-remap_append.json (located /work/intel-core/credentials/, sha256 0f5091f4f1f020e17e3ce8e4027dca471669ecb2ac33deb0c5427118795a7241 — VERIFIED) = 3:
  {d540704a, 6fa2307a, bb75e81d} — all gcp_apikey class (rider google_api_key/crash_reporting d540704a, rider google_maps 6fa2307a, driver google_api_key/crash_reporting/maps bb75e81d). All three sit in the append's verdict_updates as "byte-identical to prior census" (2026-09-17, DA.147.0/CA.225.0 auth-remap static diff) → PRIOR COVERAGE; no new material, no leak. The append's only genuinely-new credential that day (d4bca767, public-by-design web-analytics token, prelive SPA HTML) is NOT in catalog22 ✓.

(ii) catalog22 ∩ braze_neveruse 72-key set = 0 → braze_neveruse_matches=[] RE-CONFIRMED (authoritative 72 = 66 live / 4 dead / 2 not-a-cred; receipt 11 §B).

(iii) catalog24 ∩ /work/lane34/sts_verdicts.tsv (headerless, 186 rows; 147 DEAD / 39 KEYID-EXISTS incl. PRIORITY 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085) = 0 → no AWS cross-pairing from mobile corpora.

Do-not-burn guard: sha8s {94cd0fc8, 5771ae40, 6a1e88d1, 8aa2d085, 81976adb} ABSENT from every mobile set and from all printed intersections ✓ (untouched; zero STS activity this phase).

## Attestations
Zero network/DNS; zero validation; zero STS; read-only; sha8-only; zero PII; zero credential values; register ×3 untouched; SSOT-append verified by full sha256 before use.
