# CyberStrike Gateway

`cyberstrike-gateway` is the private, independently authored policy boundary between agent
runtimes, the external AGPL CyberStrike plugin, and security-tool backends. The runtime-facing MCP
surface is deliberately fixed to three tools:

- `harness_bridge_status`
- `harness_capabilities`
- `harness_invoke`

There is no generic RPC, shell, resource, prompt, raw backend, or direct companion registration.
The closed manifest contains 171 backend security capabilities (38 cloud-audit, 39 GitHub
Security, 41 CVE, 37 OSINT, and 16 Metasploit) plus ten approved Codex/fan-out bridge
capabilities. Exact upstream wire-schema hashes are recorded separately from the gateway's
hardened policy-overlay hashes so a local policy change cannot be misreported as upstream drift.

## Current fail-closed state

Backend launch is intentionally unavailable. The repository does not yet prove Windows Job
Object ownership with kill-on-close semantics, so every security backend remains discoverable
with `windows_job_object_containment_unverified`. No backend process is started by this package in
that state. The two Metasploit session command-channel capabilities are permanently denied as C2,
and content-level C2 detection runs before engagement grants.

An invocation must match the canonical manifest revision and its capability schema, reserve a
UUID idempotency key, pass permanent-deny classification, pass verified runtime containment,
carry a verified manifest-bound unexpired engagement, and provide fresh confirmation for mutable,
external-submission, billable, or high-risk operations. Backend responses are deeply redacted and
bounded before they reach MCP or HTTP. Audit receipts contain allowlisted metadata and hashes,
never raw arguments or results.

## Transports

The local MCP endpoint uses newline-delimited JSON-RPC over stdio. The companion plugin bridge uses
an HMAC-authenticated HTTP hub bound only to `127.0.0.1`. HTTP request bodies are capped at 64 KiB;
responses are capped at 256 KiB so the complete closed manifest remains discoverable. The hub
rejects non-loopback peers, Host mismatches, Origin and forwarding headers, query strings,
chunked requests, clock skew, bad signatures, and nonce replays.

The launcher requires these pre-existing environment bindings and never creates or rotates them:

- `CYBERSTRIKE_HARNESS_URL` — exactly `http://127.0.0.1:<port>/`
- `CYBERSTRIKE_HARNESS_HMAC_KEY_B64` — canonical base64 encoding of exactly 32 bytes
- `CYBERSTRIKE_HARNESS_AUDIT_PATH` — absolute path to the append-only NDJSON receipt file

Do not put secret values in repository files, command arguments, logs, or documentation.

## Static validation

From this directory on Node 22.6 or newer:

```powershell
node --experimental-strip-types --test "test/*.test.ts"
node --experimental-strip-types --experimental-test-coverage --test-coverage-lines=80 --test-coverage-branches=80 --test-coverage-functions=80 --test "test/*.test.ts"
node --experimental-strip-types scripts/inventory-census.ts
node --experimental-strip-types scripts/verify-boundary.ts
```

These checks use mocks and static inventories. They do not launch CyberStrike, Metasploit,
companions, Docker, or the gateway listener.
