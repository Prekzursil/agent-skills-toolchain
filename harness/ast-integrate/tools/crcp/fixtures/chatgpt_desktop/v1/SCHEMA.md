# ChatGPT Desktop Fixture Schema v1

Generated: 2026-07-20T00:08:58.920701+00:00

## Bundle layout

```
fixtures/chatgpt_desktop/v1/
  MANIFEST.json
  SCHEMA.md
  raw_stream/snap_NNN_bytesXXXX.json   # unique progressive stream snapshots
  raw_conversation/conversation_<hash12>.json
```

## StreamSnapshot (UI-layer)

- Progressive snapshots of the same Desktop stream (size grows over time).
- **No reliable message text** — hashes, lengths, directives, metadata only.
- Identity: content `sha256` + `bytes`.
- Unique snapshots: **13** from **13** files.
- Progressive by size: **True**

### Unique snapshot ladder
- snap_000: bytes=91 sha256=c8fe522b01eb4118… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (1).json
- snap_001: bytes=91 sha256=9deb9bd6fd6c505a… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (2).json
- snap_002: bytes=91 sha256=d182668a54c57920… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (3).json
- snap_003: bytes=91 sha256=7bd08d36589f8fcd… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace.json
- snap_004: bytes=56837 sha256=530d4ba0bd626b3e… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (4).json
- snap_005: bytes=153335 sha256=c990a8ae2632a144… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (5).json
- snap_006: bytes=172627 sha256=40bf8d4575927771… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (6).json
- snap_007: bytes=172627 sha256=9e43825cadcd1acc… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (7).json
- snap_008: bytes=191919 sha256=4657fedcf4c1a286… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (8).json
- snap_009: bytes=230505 sha256=237fc050a3ecb42e… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (10).json
- snap_010: bytes=230505 sha256=217076da51385728… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (11).json
- snap_011: bytes=230505 sha256=6e26d112c7f1f377… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (9).json
- snap_012: bytes=288415 sha256=b0a9ce7cc3e7c42a… hash_like=0 text_like=0 file=chatgpt-conversation-stream-trace (12).json

## ConversationExport (content)

- Full export for conversation family `6a5d2b66-a160-8327-9b06-baca0caf1584`.
- Files on disk: **3**; unique content: **1**.
- All identical: **True**

### Content stats (deduped export)
- mapping_nodes: None
- roles: None
- content_types: None
- total_text_chars: None
- has_real_text: None

## Ingestion rule for CRCP bus

1. Prefer **ConversationExport** for payload text / research packs.
2. Use **StreamSnapshot** series only for protocol/schema regression and UI event taxonomy.
3. Drop-folder path: place new exports under `inbox/chatgpt/` → normalizer produces bus envelopes with `payload_ref` pointing at conversation fixture, optional `stream_trace_ref` for progressive meta.
