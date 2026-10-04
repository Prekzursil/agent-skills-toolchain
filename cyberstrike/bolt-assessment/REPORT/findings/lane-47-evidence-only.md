# LANE-47 EVIDENCE-ONLY ROWS — subtask 107 (2026-10-03) — no new vul_* id minted
# HELD verdicts and negative-surface observations that carry evidence but no vulnerability delta.
# Authority table: /work/bolt/REPORT/receipts/lane-47/f-verdict-table.txt

## 1. MQTT-WS CONNECT gates — rider & driver brokers — HELD (fail-silent, unchanged)
- rider-broker.ws.bolt.eu/mqtt — client l47probe-c41054-rider: TLSv1.3 (TLS_AES_256_GCM_SHA384),
  HTTP/1.1 101 upgrade (subprotocol mqtt, origin https://bolt.eu), MQTT v3.1.1 CONNECT sent,
  0 bytes returned, read timeout at 7209 ms.
- driver-broker.ws.bolt.eu/mqtt — client l47probe-c41054-driver: same handshake profile, 0 bytes,
  read timeout at 7170 ms.
- Baseline lane-35 (2026-10-01): 7174 / 7169 ms — deltas +35 ms / +1 ms. CONNACK never sent on either
  day; no WS close frame, no error — the gate silently discards unauthenticated CONNECTs after ~7.2 s.
- Verdict: authentication gate HELD, timing oracle stable (constant ~7.17-7.21 s window). No new exposure.
- Discipline: fresh client IDs (l47probe-*), no SUBSCRIBE, no credentials attempted, single attempt each.

## 2. beehive.bolt.eu SNI edges — EXACT PARITY — HELD
- Edge 172.65.240.204 and 172.65.223.108 both: HTTP/2 200, 14174 B, body sha8 042c2c71 (byte-identical
  between edges and to lane-35 snapshot), etag "e9db2e98f5973ed72e1d02ef890a651a",
  last-modified Thu 13 Aug 2026 07:40:49 GMT, server: envoy, x-amz-request-id + x-amz-id-2 present
  (S3-backed), HSTS max-age=31536000 includeSubDomains.
- CSP + CSP-report-only headers present and unchanged vs lane-35 (incl. media-src
  https://s3.eu-central-1.amazonaws.com/bolt-voice-call-records/, script-src static.bolt.eu /
  googletagmanager / maps.googleapis).
- NEW-INTEL sweep (hostname/S3/bucket regex over both bodies + headers): **NONE** — no hostnames or
  bucket references beyond the baseline-known set. Interstitial static since 2026-08-13 (unmodified asset).

## 3. menu-food.prelive.bolt.eu — Basic-auth posture — HELD (see vul_07a35e2d1001 addendum)
Single control endpoint (/api -> 401 Basic) re-confirmed; the /health bypass and cluster-name
disclosure unchanged. Body sha8 delta on /api explained as Cloudflare per-request script injection
(unique CF-Ray embedded), underlying Apache stub identical.

## 4. beehive-bolt-eu.applog.bolt.eu — CLOSED at probed paths (negative evidence)
POST /beehive/csp/report -> 404 (empty body); POST /app-log/beehive/csp/report -> 404 (empty body).
No Fastify error stub (contrast: node.bolt.eu returns structured JSON errors) — different router or
absent route. Bounds the open ingestion surface to node.bolt.eu + beehive-csp.applog.bolt.eu.

## 5. Budget / discipline attestation
13 counted HTTP/WS calls of 25 budgeted (2 sentinel calls excluded per subtask terms); >=1.2 s pacing
between calls (budget.jsonl timestamps prove <=1 rps); single attempt per endpoint per shape; no
subscription; no credential brute-force; no OOB infrastructure; NEVER-ROTATE honored (zero credentials
submitted anywhere in lane-47); all payloads synthetic l47probe-*/non-PII; leak-gate clean (no raw
credential shapes, no PII values — verified over all lane-47 artifacts before sealing).
