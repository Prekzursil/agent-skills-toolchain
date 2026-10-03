
===== LANE-41 CH-2 SAVED-QUERY CORPUS MINING (memo-gated stage 3) — 2026-10-02T18:37:35Z =====
request# at start: 11/20 chain_spend={'CH1': 6, 'CH4': 5, 'CH2': 0} aborted=False
[2026-10-02T18:37:35Z] #12 ch2-page-1 sha8=4c5f245f GET RAW url-sha8=b5700432
  -> HTTP 401 (0.17s)
  body: {"error_code":401,"message":"Credential was not sent or was of an unsupported type for this API. [ReqId: 405af6fc-eb6e-4885-8bc1-82f9adfc5bf1]"}
[2026-10-02T18:37:36Z] #13 ch2-page-2 sha8=4c5f245f GET RAW url-sha8=a8b64e13
  -> HTTP 401 (0.1s)
  body: {"error_code":401,"message":"Credential was not sent or was of an unsupported type for this API. [ReqId: a2f9307e-4b09-4152-b515-24d9e4c1a61d]"}
[2026-10-02T18:37:37Z] #14 ch2-page-3 sha8=4c5f245f GET RAW url-sha8=f8f6706a
  -> HTTP 401 (0.1s)
  body: {"error_code":401,"message":"Credential was not sent or was of an unsupported type for this API. [ReqId: 9d7c5bca-c781-4c01-b59c-8111f2fbf253]"}
===== CH-2 PARTIAL — 0 credential-shape hits over 0 query texts — 2026-10-02T18:37:37Z — budget 14/20 chain_spend={'CH1': 6, 'CH4': 5, 'CH2': 3} =====

--- CH-2 SUMMARY (2026-10-02T18:37:37Z) ---
verdict: PARTIAL
pages: [{"page": 1, "parse": "OK", "n": 0, "count": null}, {"page": 2, "parse": "OK", "n": 0, "count": null}, {"page": 3, "parse": "OK", "n": 0, "count": null}]
queries_seen: 0  with_text: 0  owners(sha8-set size): 0
credential-shape hits: 0 (sha8 + shape-class only; zero plaintext persisted)
hits: []

===== LANE-41 CH-2 RESUME (authenticated pulls; prior 3x401 anonymous) — 2026-10-02T18:38:15Z =====
request# at start: 14/20 chain_spend={'CH1': 6, 'CH4': 5, 'CH2': 3} aborted=False
[2026-10-02T18:38:17Z] #15 ch2-auth-page-1 sha8=4c5f245f GET /api/2.0/preview/sql/queries
  -> HTTP 200 (1.97s)
  body: {"count": 265, "page": 1, "page_size": 100, "results": [{"id": "0abca9a6-8426-4294-aa27-da950bcee02c", "name": "New Query 2026-10-02 15:02:45", "description": null, "query": "<REDACTED>", "is_draft": false, "updated_at": "2026-10-02T12:03:57Z", "created_at": "2026-10-02T12:02:46Z", "data_source_id": null, "options": {"parent": "folders/2689739659068759", "folder_node_status": "ACTIVE", "folder_nod
[2026-10-02T18:38:18Z] #16 ch2-auth-page-2 sha8=4c5f245f GET /api/2.0/preview/sql/queries
  -> HTTP 200 (1.32s)
  body: {"count": 265, "page": 2, "page_size": 100, "results": [{"id": "22139ce9-2b5c-40a1-89d3-7d9219d445db", "name": "UA Users affected.sql", "description": null, "query": "<REDACTED>", "is_draft": false, "updated_at": "2026-04-17T13:23:33Z", "created_at": "2026-04-16T08:34:09Z", "data_source_id": "44c55be5-f025-49b2-bbc0-a7cad79b4d47", "options": {"parent": "folders/212286361577565", "apply_auto_limit"
[2026-10-02T18:38:19Z] #17 ch2-auth-page-3 sha8=4c5f245f GET /api/2.0/preview/sql/queries
  -> HTTP 200 (1.12s)
  body: {"count": 265, "page": 3, "page_size": 100, "results": [{"id": "b6f106cb-59ca-49a6-8c8a-b43de7561cf0", "name": "Blast Dispatch check", "description": null, "query": "<REDACTED>", "is_draft": false, "updated_at": "2025-12-16T11:51:17Z", "created_at": "2025-12-16T09:39:49Z", "data_source_id": "44c55be5-f025-49b2-bbc0-a7cad79b4d47", "options": {"parent": "folders/1807196956597019", "apply_auto_limit"
===== CH-2 DEMONSTRATED — 0 hits / 265 query texts — 2026-10-02T18:38:19Z — budget 17/20 chain_spend={'CH1': 6, 'CH4': 5, 'CH2': 6} =====

--- CH-2 SUMMARY (resume, 2026-10-02T18:38:19Z) ---
prior anonymous 401s: 3 (no PAT attached — raw_url header-skip; zero credential exposure)
verdict: DEMONSTRATED
pages: [{"page": 1, "parse": "OK", "n": 100, "count": 265}, {"page": 2, "parse": "OK", "n": 100, "count": 265}, {"page": 3, "parse": "OK", "n": 65, "count": 265}]
queries_seen: 265  with_text: 265  owners(sha8-set): 62
credential-shape hits: 0 (sha8 + shape only)
hits: []
