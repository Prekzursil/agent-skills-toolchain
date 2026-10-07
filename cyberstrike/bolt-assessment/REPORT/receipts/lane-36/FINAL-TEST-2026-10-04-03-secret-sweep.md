# FINAL-TEST-2026-10-04-03 — LANE-36 STAGE A — SECRET-SHAPE CATALOG & CROSS-PAIRING (subtask 132)

- Round: FINAL-TEST (directive 2026-10-04). Subtask: 132. Mode: OFFLINE, catalog-only. **Zero validation attempts, zero network.**
- Sweep surfaces (6 corpora per app where applicable): apktool-decoded AndroidManifest/res/values strings, assets/, jadx java trees, raw `strings` dumps on inner APKs, XAPK manifest metadata, split configs.
- Sweep script persisted: /work/lane36/secret_sweep.py (regex classes below). Catalog artifacts: analysis/secret_catalog.json (+ .tsv), analysis/secret_triage.md.

## A. Regex classes swept

AWS access-key-id shapes (AKIA/ASIA + 16 uppercase alnum); GCP API-key shapes (AIza + 35 base64url chars, class regex not reproduced); GitHub PAT prefixes (ghp/gho/ghu/ghs families + classic 40-hex); Braze (app_id + braze.com endpoints + SDK keys); Sinch (app key/secret ctx, sinch.com); Sentry DSN https://[0-9a-f]{32}@…sentry…; Firebase/google-services.json fields; Maps keys (geo/maps meta); JWT compact JWS three-segment tokens; Bearer tokens; PEM PRIVATE-KEY block headers (5-dash BEGIN delimiter regex not reproduced).

## B. Catalog totals (catalog-only, sha8-only)

- Entries: **131** (client 19 / driver 112). Distinct value-sha8 count: 23. *(2026-10-04 addendum: +1 client pem_block discovered by the dex-level extended leak-gate during receipt sealing — see §C.)*
- Per-class per-app (hits): client — gcp_apikey 5, github_pat 11 (all FALSE-override), braze_uuid_key 1, sentry_uuid_key 1, pem_block 1 (public test material, addendum); driver — gcp_apikey 4, github_pat 104 (93 = single sha8 d680cca6 from sentry-external-modules.txt build-hash lines; all FALSE-override), pem_block 2 (public test material), sentry_uuid_key 1, uuid_generic_keyctx 1.

## C. TRUE positive catalog (sha8 of VALUE only)

| sha8 | class | app | context |
|---|---|---|---|
| cb363510 | braze_uuid_key | client | strings.xml braze endpoint sdk.fra-02.braze.eu + app_id |
| 6fa2307a | gcp_apikey (maps) | client ×2 | com.google.android.geo maps meta-data |
| d540704a | gcp_apikey (api/crash) | client ×3 | google-services api_key |
| bb75e81d | gcp_apikey (api/crash/maps) | driver ×4 | google-services + geo meta |
| bf2e62e3 | sentry_uuid_key | client | Sentry init |
| 93196d68 | sentry_uuid_key | driver | Sentry init |
| 1d4cdc12 | uuid_generic_keyctx | driver | funnel.API_KEY (uuid-shaped) |
| 480c7b4a | gcp_apikey (geo.API_KEY) | both | AndroidManifest geo meta-data |
| 22cc2e31 | crashlytics 40-hex | driver | com.crashlytics.ApiKey meta |
| fc0a4b72 / d9208535 | google_app_id | client / driver | google-services.json |

- Sinch, JWT, Bearer, AWS secret shapes: **0 hits in both trees.**
- pem_block ×2 (driver, marker sha8 3021d90e) + ×1 (client, **addendum**): netty SslUtils **public** PROBING_KEY/PROBING_CERT constants (upstream netty test material). Addendum: dex-level extended leak-gate on at_client/classes5.dex found the same PEM block embedded client-side at offset 5786567 with `io/netty/handler/ssl/SslUtils` and `PROBING_CERT`/`PROBING_KEY` string-pool refs adjacent in the same dex (offsets 6203805/6480448/6480462); full-block value-sha8 **f92c2209** byte-identical in client and driver classes5.dex — one shared public constant, class FALSE (public, not credentials). No other PEM/private-key material anywhere in either tree.

## D. AWS key-ID cross-pairing (KEY DELIVERABLE for stage B)

- AKIA/ASIA hits in both apps: **ZERO**. Cross-pair table (APK-keyid-sha8 ↔ lane-34 verdict) = **EMPTY**.
- Intersection with the 39 KEYID-EXISTS sha8 list: **0/39** (incl. PRIORITY six 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085 — none present).
- Lane-34 corpus union unchanged: 186 distinct key IDs, 147 DEAD / 39 KEYID-EXISTS / 0 LIVE (STS oracle, subtask 125). No new pairs handoff → stage-B key-validation budget remains 0 consumed.
- Do-not-burn honored: DEAD 94cd0fc8 / 5771ae40 / 6a1e88d1 and EXPIRED 8aa2d085 / 81976adb absent from both trees — nothing re-touched.

## E. Braze never-use cross-reference

- Catalog located: /work/lane36/braze_neveruse_sha8.txt — recovered from lane-37 Kuzu graphdb (/work/lane37/graphdb), 72 key-lines (header anomaly: source header says 73; off-by-one documented, deferred to stage B).
- Intersection with app Braze material (cb363510 + endpoint): **0 matches** — app Braze key is not among the 66/72 never-use corpus.

## F. Leak-gate

Deliverable set (receipts + analysis reports + manifests): AKIA-shape / AIza-shape / JWT-header / GitHub-token / PEM-BEGIN / URL-userinfo patterns → **0 hits** (gate log sealed with SHA256SUMS.lane-36). Working-tree extended check (private-key block headers across jadx/apktool/strings corpora): only the 3 cataloged netty public probing constant occurrences (§C, incl. client addendum f92c2209) — zero unknown private-key material. Time-boxed skips: jadx_client java-tree PEM grep hit the 60 s box (rc=124) — equivalently covered by the at_client dex-level scan (rc=0, cataloged hit) and by the client strings-dump scan (0 hits); at_driver smali-tree grep hit the 60 s box (rc=124) — covered by jadx_driver java-tree (rc=0, netty-ssl-only) and strings_driver.txt (netty marker only).

## G. Attestation

Catalog-only. No value decoded, validated, or transmitted. No PII recorded (uuid-shaped identifiers fingerprinted sha8-only). Zero Bolt-estate network. NEVER-ROTATE intact.
