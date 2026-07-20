# CRCP P1 Envelope v1.1

## Summary

Implemented an additive CRCP envelope v1.1 contract and a filesystem-backed,
content-addressed artifact store using only the Python standard library.

The envelope builder now emits `schema: crcp.envelope.v1.1` while retaining
`v: 1` for major-version dispatch compatibility. It adds `event_key`,
`trace_id`, and `kind`; accepts explicit values for all three; and generates
safe defaults when omitted. Generated event keys are deterministic for the
same routing, thread, kind, and payload identity. Existing local file
`payload_ref` values are converted to canonical `sha256:<hex>` references when
the file is readable. Existing content addresses are normalized, while opaque
or unresolved legacy references are retained for backward compatibility.

`validate_envelope(env)` accepts both `crcp.envelope.v1` and
`crcp.envelope.v1.1` and returns `(ok, errors)` without mutation. Validation
covers required fields and types, timezone-aware timestamps, hash and content
reference syntax, mutually exclusive inline/reference payloads, non-negative
payload sizes, and agreement between a content-addressed reference and its
declared payload digest. The v1.1-only fields are not required from v1 input.

The artifact store writes to `<root>/sha256/<first-two-hex>/<remaining-hex>`.
Writes use a same-directory temporary file, flush and `fsync`, then atomic
replacement. Repeated writes are idempotent, references are strictly parsed to
prevent path traversal, and reads verify content integrity. Both an
`ArtifactStore(root)` API and the requested module-level `put_bytes(data)` and
`get(ref)` API are provided. The default root can be selected with
`CRCP_ARTIFACT_STORE` and otherwise uses `~/.crcp/artifacts`.

## Files

- `envelope.py` — full replacement module, 230 lines.
- `artifact_store.py` — new full module, 97 lines.
- `p1-envelope-v11.md` — this implementation and verification report.

## Wiring into existing modules

The new `make_envelope` signature is additive: every prior argument and default
remains supported, and the existing `content_hash`, `utc_now`, and
`write_envelope` entry points remain available. Therefore current imports from
`bridge.py`, `inbox.py`, and `token_watch.py` continue to resolve unchanged.

An integration smoke test overlaid the delivered `envelope.py` onto a temporary
copy of the existing `crcp` package, invoked
`bridge.export_conversation_pack`, read its output envelope, and successfully
validated it as v1.1 with a content-addressed payload reference. No write to the
read-only source tree was performed.

Consumers that persist large payloads should construct
`ArtifactStore(configured_root)`, call `put_bytes`, and pass the returned
`sha256:<hex>` value as `payload_ref`. Readers resolve that reference through
the same configured store with `get`. Legacy v1 envelopes and unresolved
legacy path references remain readable during migration.

## Self-tests

All tests passed on the Linux Databricks job node:

- Python compilation of both delivered modules.
- v1.1 construction and validation, including required additive fields.
- backward validation of a representative v1 envelope with a legacy path.
- conversion of an existing local payload path to its SHA-256 content address.
- deterministic event-key generation for equivalent logical inputs.
- rejection of malformed content references and inconsistent payload digests.
- rejection of simultaneous inline payload and payload reference.
- artifact put/get round trip and exact digest verification.
- 32 concurrent idempotent puts of identical bytes.
- malformed/traversal-like reference rejection.
- stored-content corruption detection on read.
- module-level default-store API and non-bytes input rejection.
- integration with existing `bridge.export_conversation_pack`.

Delivered module SHA-256 digests:

- `envelope.py`: `68d4ee96a0933de2b6e4d05475b5bd1805abc7631a1a6cbeff156756818b79b7`
- `artifact_store.py`: `8b645953111ddc0d948f9ad7f8565c3cb4204a5367be5426d8e452c35b3cbbd5`

UNIT-COMPLETE: p1-envelope-v11
