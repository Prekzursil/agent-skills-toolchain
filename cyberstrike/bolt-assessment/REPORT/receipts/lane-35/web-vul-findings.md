# LANE-35 NEW FINDINGS — vul_ register additions (subtask 83; executed 2026-10-01 22:26–22:42Z; sealed 2026-10-02)

## vul_07a35e2d1001 — menu-food.prelive.bolt.eu `/health` Basic-auth bypass + envoy cluster-name disclosure
- Severity: MEDIUM (auth-bypass class, prelive-scoped; no data exposure)
- Class: Authentication bypass (scope-limited) / infrastructure information disclosure
- Baseline (SSOT §2 live-verified 06.09; lane-31 2026-10-01): food.prelive.bolt.eu and
  menu-food.prelive.bolt.eu = 72/72 endpoints Basic-auth-gated (401).
- Measurement (2026-10-01T22:41:13.791Z, single GET, no credentials):
  `GET https://menu-food.prelive.bolt.eu/health` → **200**, 81 ms, 0-byte body
  (body sha8 e3b0c442), `X-Robots-Tag: noindex`,
  **`x-envoy-upstream-healthchecked-cluster: prelive-euc-1-public`**
  (CF-RAY a43ef93d6a54ae3a-WAW, cf-cache-status DYNAMIC).
  Sibling-vhost control (22:41:07.632Z): `GET https://food.prelive.bolt.eu/health` → 401
  Basic realm="Restricted" (157 ms, 12 B, body sha8 d089c8a9) — misconfiguration is
  menu-food-vhost-local, NOT estate-wide.
  Subset sample verdict: 11/12 sampled endpoints 401 (food 6/6; menu-food 5/6) — menu-food
  extrapolates to ~71/72, i.e. the held "72/72" posture no longer holds.
- Impact: (1) unauthenticated origin-reachable endpoint on the prelive plane;
  (2) public disclosure of internal envoy cluster identity and region topology
  (`prelive-euc-1-public` → EU-central-1 prelive cluster naming);
  (3) invalidates the uniform-gating assumption for the menu-food vhost;
  (4) provides a liveness/oracle primitive for origin mapping in lane-47 follow-up.
- Remediation: extend the Basic gate to `/health` on menu-food.prelive.bolt.eu; strip
  `x-envoy-upstream-healthchecked-cluster` from externally visible responses.
- Evidence receipt: web-e-food-basic-sample.txt (receipt lines 133–141; food control 62–64).

## vul_07a35e2d1002 — node.bolt.eu `/app-log/node/csp/report` anonymous log ingestion (open sink)
- Severity: LOW (CSP collectors are commonly unauthenticated by design; no reflection, no data exposure; prod BFF plane)
- Class: Unauthenticated ingestion / log-injection into observability pipeline
- Baseline: CSP `report-uri /app-log/node/csp/report` observed in node.bolt.eu response
  headers during lane-31; never probed before this lane.
- Measurement (2026-10-01T22:34Z, single-attempt per shape, synthetic non-PII payloads):
  `POST /app-log/node/csp/report` with `csp-report` JSON envelope → **200
  `{"code":0,"message":"OK"}` in 50 ms**; ndjson log-line shape → **200**. No
  Authorization/Cookie headers were ever sent — the route is anonymously writable.
  Scoping probes: `POST /app-log` → 404; `POST /app-log/node` → 404; `GET` on the sink → 404;
  `OPTIONS` → 200 `allow: POST` (Fastify route-level routing, consistent with the 404-oracle family).
- Impact: anonymous writers can inject forged CSP reports and synthetic log lines into the
  rental-web observability pipeline — log pollution, cardinality/storage-cost abuse, and
  alert-noise generation that could mask real telemetry. Endpoint sits on the production
  BFF singleton node.bolt.eu.
- Remediation: add lightweight attestation (origin allowlist, per-app sampling token, or
  signed report submission) on ingestion routes; strict `csp-report` schema validation;
  rate-limit per source.
- Evidence receipt: web-a-node-bff.txt.

## NEW-INTEL deltas (no vul id minted — register-ingest candidates for subtask 88)
- **applog.bolt.eu** — NEW, previously unknown subdomain family disclosed by the beehive
  CSP (report-only): `beehive-bolt-eu.applog.bolt.eu` (connect-src log-ingest endpoint) and
  `beehive-csp.applog.bolt.eu` (CSP report-uri). The pattern
  `<app>-csp.applog.bolt.eu/<app>/csp/report` mirrors node.bolt.eu
  `/app-log/<app>/csp/report`, suggesting a shared multi-app ingestion platform → lane-47
  candidates.
- beehive.bolt.eu CSP additionally discloses: S3 buckets `bolt-voice-call-records`
  (s3.eu-central-1.amazonaws.com media/connect-src), `upload.taxify.eu`,
  `bolt-verification-documents` (+ s3-accelerate variant), `taxify-fleet`;
  internal-TLD WS wildcard `wss://*.boltint.net`; Sinch API plane
  (ocra-euc1.api.sinch.com, *.api.sinch.com); Sentry ingest (*.ingest.de.sentry.io /
  *.ingest.sentry.io); frame-ancestors `https://bolt.docebosaas.com` +
  `cdn5.dcbstatic.com` (Docebo LMS embedding → beehive is an internal learning/support tool).
- NEW-NEGATIVE: `dim_beehive_queue_config` queue names do NOT surface in any interstitial
  body or routing hint (grep clean); hardcoded table/model identifiers are NOT injectable
  on node.bolt.eu / api.iam.bolt.eu (uniform 403 image-envelope / 404 zero-byte, zero
  reflection) — see web-f-injectability.txt.

## Rule compliance for both findings
Single-attempt per (key,endpoint) (a single re-attempt only on explicitly re-measured
gates); synthetic non-PII payloads only; sha8-only fingerprints in chat/receipts; no
credentials used anywhere in lane-35 stream 1; ≥1.2 s pacing enforced by harness
/work/lane35/h35.py; WATCH7 (testregistry.bolt.eu) untouched; leak-gate grep over receipts
clean (no eyJ/Bearer/Braze/ghp_/AKIA shapes); zero PII values in artifacts.
