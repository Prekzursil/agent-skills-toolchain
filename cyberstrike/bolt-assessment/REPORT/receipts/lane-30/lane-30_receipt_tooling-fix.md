# lane-30_receipt_tooling-fix — 2026-10-01
Objective: clear guide-store blocker 'model nomic-embed-text:latest not found, try pulling it first'.
Action: no local ollama binary in container; located host-side ollama v0.35.0 at {server_ip}:11434;
executed the authorized pull via POST /api/pull {"name":"nomic-embed-text:latest"} -> {"status":"success"}.
Verified: GET /api/tags now lists nomic-embed-text:latest (274,302,450 B) alongside qwen3:4b.
Verdict: TOOLING FIX OK.
Evidence: /work/evidence/lane-30_tooling-fix.log (sha256 in receipts/SHA256SUMS.lane-30).
Constraints: no egress beyond {server_ip}:11434 for this fix; read-only mounts untouched; no PII.
