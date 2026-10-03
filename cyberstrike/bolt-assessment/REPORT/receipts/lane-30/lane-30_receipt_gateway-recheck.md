# lane-30_receipt_gateway-recheck — 2026-10-01
Objective: fresh UP/DOWN verdict + 31100 listener confirmation after the sealed restart receipt.
Timeline: UP 17:31:36Z (pid 9036, harness_bridge_status, sealed receipt) -> HUNG by 17:41Z.
Findings (17:45:29Z): TCP connect to {server_ip}:31100 SUCCEEDS; HTTP/MCP dead
(initialize -> TimeoutError: timed out; bare GET -> HTTP 000, curl exit 28); host bridge healthy
(ollama 11434 answers instantly) -> fault isolated to the estate-side gateway process.
Verdict: GATEWAY DOWN/HUNG. LISTENER 31100: TCP-accepting YES / HTTP-serving NO.
Blocker (verbatim): TimeoutError: timed out — restart requires estate-side operator
(gateway-stop.ps1 -> Start-ScheduledTask CyberStrikeGateway -> gateway-health.ps1); container-side
restart already exhausted its 3 documented attempts (see sealed phase0 receipt).
Evidence: /work/evidence/lane-30_gateway-recheck.log (sha256 in receipts/SHA256SUMS.lane-30).
Constraints: health-check probes only; no restart executed container-side; fail-closed reporting; no PII.
