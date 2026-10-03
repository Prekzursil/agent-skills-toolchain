# REPORT WORKSPACE CONVENTIONS — Bolt engagement Phase 0+

Mirror of: `D:\opt\home-data\bolt\REPORT\` → container: `/work/bolt/REPORT/`
Established: 2026-10-01 (Phase 0 pre-flight, lane 30)

## Directory layout

- `phase0/` — Phase 0 pre-flight receipts (gateway restart, mount verification, snapshots)
- `receipts/lane-31/` … `receipts/lane-42/` — one subdir per engagement lane

## Receipt naming (mandatory)

Every lane writes per-receipt files named:

```
lane-XX_receipt_<slug>.<ext>
```

Examples: `lane-33_receipt_databricks-external-links.txt`,
`lane-36_receipt_apk-endpoint-delta.md`

## Artifact integrity (mandatory)

Every artifact gets a sha256 recorded in the lane's checksum file:

```
receipts/SHA256SUMS.lane-XX
```

Regenerate with: `cd /work/bolt/REPORT && sha256sum <artifact> >> receipts/SHA256SUMS.lane-XX`

## Leak gates (mandatory)

- Receipts and ALL chat-facing output must contain **zero PII values**
- **No raw credential shapes** in any chat-facing output: no `eyJ…` (JWT),
  no `Bearer` tokens, no Braze keys
- Chat carries **sha8 fingerprints only** (first 8 hex of sha256); plaintext
  credential material stays on disk only, inside the intel mounts
- NEVER-ROTATE: discovered credentials are reported, never used or rotated
  (third-party victim credentials: report only, never use)

## Mount hygiene

- `/work/bolt-intel/` and `/work/intel-core/` are read-only engagement intel —
  never modified
- All agent-generated evidence goes under `/work/bolt/REPORT/` (and raw command
  logs under `/work/evidence/` per sandbox convention)

## Gateway health sentinel (added Phase 0 close-out, 2026-10-01)

- Before each lane's FIRST bridge call and after >5 min bridge idle, run the sentinel:
  `curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://172.17.0.1:31100`
  expecting **HTTP 406** (healthy StreamableHTTP-MCP behavior on `/mcp`). A 404 on the root
  path likewise proves HTTP-serving; the HUNG signature is TCP-accept with HTTP never
  answering (`HTTP 000`, curl exit 28).
- On non-406/timeout: attempt **exactly ONE** `harness_bridge_status` (read timeout **>=90 s**
  if the gateway process may be freshly started — first call lazily probes 28 backends).
  Still failing -> **fail-closed** (lane does not proceed via bridge) + operator item in
  `phase0/OPERATOR-ACTIONS.md`.
- **Never** use `harness_invoke` for health checks. Never re-run `harness_capabilities`
  without explicit authorization (one-shot manifest ops only).
