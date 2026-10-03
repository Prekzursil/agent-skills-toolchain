
===== LANE-41 CH-4 DELTA-LAKE-SENSITIVE WRITE-SCOPE MARKER (SECONDARY) — 2026-10-02T18:34:54Z =====
request# at start: 6/20 chain_spend={'CH1': 6, 'CH4': 0, 'CH2': 0} aborted=False
[2026-10-02T18:34:55Z] #7 ch4-baseline-count sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (0.98s)
  body: {"statement_id":"01f1be8f-f68b-1a81-9aaf-993eb5b7e5d5","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":2,"columns":[{"name":"total","type_text":"BIGINT","type_name":"LONG","position":0},{"name":"own","type_text":"BIGINT","type_name":"LONG","position":1}]},"total_chunk_count":1,"chunks":[{"chunk_index":0,"row_offset":0,"row_count":1}],"total_row_count":1,"t
  SQL-RESULT: state=SUCCEEDED cols=['total', 'own'] n_rows=1 hash-only
[2026-10-02T18:34:58Z] #8 ch4-insert-marker sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (2.04s)
  body: {"statement_id":"01f1be8f-f746-1001-a9a4-73dd6d573a57","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":2,"columns":[{"name":"num_affected_rows","type_text":"BIGINT","type_name":"LONG","position":0},{"name":"num_inserted_rows","type_text":"BIGINT","type_name":"LONG","position":1}]},"total_chunk_count":1,"chunks":[{"chunk_index":0,"row_offset":0,"row_count":
  SQL-RESULT: state=SUCCEEDED cols=['num_affected_rows', 'num_inserted_rows'] n_rows=1 hash-only

===== LANE-41 CH-4 RESUME (cleanup; insert already SUCCEEDED) — 2026-10-02T18:35:31Z =====
request# at start: 8/20 chain_spend={'CH1': 6, 'CH4': 2, 'CH2': 0} aborted=False
[2026-10-02T18:35:32Z] #9 ch4-count-after-insert sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (1.11s)
  body: {"statement_id":"01f1be90-0c6b-1f23-8f8e-844b252f5f3d","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":2,"columns":[{"name":"total","type_text":"BIGINT","type_name":"LONG","position":0},{"name":"own","type_text":"BIGINT","type_name":"LONG","position":1}]},"total_chunk_count":1,"chunks":[{"chunk_index":0,"row_offset":0,"row_count":1}],"total_row_count":1,"t
  SQL-RESULT: state=SUCCEEDED cols=['total', 'own'] n_rows=1 hash-only
[2026-10-02T18:35:34Z] #10 ch4-delete-marker sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (2.02s)
  body: {"statement_id":"01f1be90-0d2a-1b84-b68f-e903000f69f5","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":1,"columns":[{"name":"num_affected_rows","type_text":"BIGINT","type_name":"LONG","position":0}]},"total_chunk_count":1,"chunks":[{"chunk_index":0,"row_offset":0,"row_count":1}],"total_row_count":1,"truncated":false},"result":{"chunk_index":0,"row_offset":
  SQL-RESULT: state=SUCCEEDED cols=['num_affected_rows'] n_rows=1 hash-only
[2026-10-02T18:35:35Z] #11 ch4-count-after-delete sha8=4c5f245f POST /api/2.0/sql/statements
  -> HTTP 200 (0.65s)
  body: {"statement_id":"01f1be90-0e58-159e-9b98-3c43f8de0c46","status":{"state":"SUCCEEDED"},"manifest":{"format":"JSON_ARRAY","schema":{"column_count":2,"columns":[{"name":"total","type_text":"BIGINT","type_name":"LONG","position":0},{"name":"own","type_text":"BIGINT","type_name":"LONG","position":1}]},"total_chunk_count":1,"chunks":[{"chunk_index":0,"row_offset":0,"row_count":1}],"total_row_count":1,"t
  SQL-RESULT: state=SUCCEEDED cols=['total', 'own'] n_rows=1 hash-only
===== CH-4 DEMONSTRATED — 2026-10-02T18:35:35Z — budget 11/20 chain_spend={'CH1': 6, 'CH4': 5, 'CH2': 0} =====

--- CH-4 SUMMARY (2026-10-02T18:35:35Z) ---
verdict: DEMONSTRATED
table(NEW prefix): main.ng_incentives.estate_lockout_probe_alvaro_20260904
marker: lane41/write-96da8fb4
counts: baseline(implied)=0 after_insert=1/own=1 after_delete=0/own=0
oracle O1-write-reach: True
oracle O2-count-01: True
oracle O3-delete: True
oracle O4-zero-residue: True
