import json, hashlib, os, re, sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone

DOWNLOADS = Path(os.environ["USERPROFILE"]) / "Downloads"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "raw_stream").mkdir(exist_ok=True)
(OUT / "raw_conversation").mkdir(exist_ok=True)

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(p: Path):
    raw = p.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return None, raw, f"json_error:{e}"
    return data, raw, None

def collect_keys(obj, prefix="", out=None, depth=0):
    if out is None:
        out = Counter()
    if depth > 8:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            out[path] += 1
            collect_keys(v, path, out, depth+1)
    elif isinstance(obj, list) and obj:
        # sample first non-null element type pattern
        for i, item in enumerate(obj[:3]):
            collect_keys(item, f"{prefix}[]", out, depth+1)
            break
    return out

def summarize_stream(data):
    """Extract structural summary; do not assume text content exists."""
    summary = {
        "top_level_type": type(data).__name__,
        "top_level_keys": list(data.keys()) if isinstance(data, dict) else None,
        "array_len": len(data) if isinstance(data, list) else None,
    }
    # progressive snapshot heuristics
    if isinstance(data, dict):
        # common shapes
        for k in ("events", "story_events", "messages", "items", "stream", "data", "turns"):
            if k in data:
                v = data[k]
                summary[f"field_{k}_type"] = type(v).__name__
                if isinstance(v, list):
                    summary[f"field_{k}_len"] = len(v)
        # nested search for event-like lists
        event_lists = []
        def walk(o, path=""):
            if isinstance(o, dict):
                for k,v in o.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(o, list):
                if o and isinstance(o[0], dict):
                    keys = set(o[0].keys())
                    if any(x in keys for x in ("type","event","opcode","message_type","channel")):
                        event_lists.append({"path": path or "root", "len": len(o), "sample_keys": sorted(keys)[:30]})
                for item in o[:2]:
                    walk(item, path + "[]")
        walk(data)
        summary["event_lists"] = event_lists[:20]
        # hash/length heavy fields
        hash_like = 0
        text_like = 0
        def count_leaf(o):
            nonlocal hash_like, text_like
            if isinstance(o, dict):
                for v in o.values():
                    count_leaf(v)
            elif isinstance(o, list):
                for v in o[:50]:
                    count_leaf(v)
            elif isinstance(o, str):
                if re.fullmatch(r"[a-fA-F0-9]{32,128}", o) or re.fullmatch(r"sha256:[a-f0-9]+", o):
                    hash_like += 1
                elif len(o) > 40 and " " in o:
                    text_like += 1
        count_leaf(data)
        summary["hash_like_strings"] = hash_like
        summary["text_like_strings"] = text_like
    return summary

def summarize_conversation(data):
    summary = {
        "top_level_keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__,
    }
    if not isinstance(data, dict):
        return summary
    # ChatGPT export shapes vary: mapping, linear_conversation, etc.
    for k in ("title", "create_time", "update_time", "conversation_id", "id", "current_node"):
        if k in data:
            v = data[k]
            if isinstance(v, str) and len(v) > 80:
                summary[k] = {"type": "str", "len": len(v), "sha256": sha256_bytes(v.encode())}
            else:
                summary[k] = v
    mapping = data.get("mapping") or data.get("messages")
    if isinstance(mapping, dict):
        summary["mapping_nodes"] = len(mapping)
        roles = Counter()
        content_types = Counter()
        total_text_chars = 0
        for node in mapping.values():
            msg = node.get("message") if isinstance(node, dict) else None
            if not isinstance(msg, dict):
                continue
            author = msg.get("author") or {}
            role = author.get("role") if isinstance(author, dict) else None
            if role:
                roles[role] += 1
            content = msg.get("content") or {}
            if isinstance(content, dict):
                content_types[content.get("content_type") or "unknown"] += 1
                parts = content.get("parts") or []
                if isinstance(parts, list):
                    for p in parts:
                        if isinstance(p, str):
                            total_text_chars += len(p)
        summary["roles"] = dict(roles)
        summary["content_types"] = dict(content_types)
        summary["total_text_chars"] = total_text_chars
        summary["has_real_text"] = total_text_chars > 0
    elif isinstance(mapping, list):
        summary["message_list_len"] = len(mapping)
    return summary

stream_files = sorted(DOWNLOADS.glob("chatgpt-conversation-stream-trace*.json"), key=lambda p: p.stat().st_size)
conv_files = sorted(DOWNLOADS.glob("chatgpt-conversation-6a5d2b66*.json"))

manifest = {
    "schema_version": "crcp.chatgpt_desktop.fixture.v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source_dir": str(DOWNLOADS),
    "streams": [],
    "conversations": [],
    "dedup": {},
    "unified_schema": {},
    "notes": []
}

# Process streams
content_hashes = defaultdict(list)
size_groups = defaultdict(list)
all_key_paths = Counter()
stream_summaries = []

for p in stream_files:
    data, raw, err = load_json(p)
    h = sha256_file(p)
    content_hashes[h].append(p.name)
    size_groups[len(raw)].append(p.name)
    entry = {
        "source_name": p.name,
        "bytes": len(raw),
        "sha256": h,
        "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        "parse_error": err,
    }
    if data is not None:
        entry["summary"] = summarize_stream(data)
        all_key_paths.update(collect_keys(data))
        stream_summaries.append((len(raw), h, p.name, entry["summary"]))
        # write canonical copy only for unique sizes later
    manifest["streams"].append(entry)

# progressive series by unique content hash sorted by size
unique_streams = []
seen_h = set()
for size, h, name, summ in sorted(stream_summaries, key=lambda x: x[0]):
    if h in seen_h:
        continue
    seen_h.add(h)
    unique_streams.append({"bytes": size, "sha256": h, "example_name": name, "summary": summ})

# copy unique stream files as snap_NNN.json
for i, u in enumerate(unique_streams):
    # find source
    src = None
    for p in stream_files:
        if sha256_file(p) == u["sha256"]:
            src = p
            break
    dest = OUT / "raw_stream" / f"snap_{i:03d}_bytes{u['bytes']}.json"
    dest.write_bytes(src.read_bytes())
    u["fixture_path"] = str(dest.relative_to(OUT))

manifest["unique_stream_snapshots"] = unique_streams
manifest["stream_progressive"] = {
    "is_progressive_by_size": all(unique_streams[i]["bytes"] <= unique_streams[i+1]["bytes"] for i in range(len(unique_streams)-1)) if len(unique_streams)>1 else True,
    "snapshot_count_unique": len(unique_streams),
    "snapshot_count_files": len(stream_files),
    "duplicate_groups": {h[:12]: names for h, names in content_hashes.items() if len(names) > 1},
}

# conversations
conv_hashes = defaultdict(list)
for p in conv_files:
    data, raw, err = load_json(p)
    h = sha256_file(p)
    conv_hashes[h].append(p.name)
    entry = {
        "source_name": p.name,
        "bytes": len(raw),
        "sha256": h,
        "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        "parse_error": err,
    }
    if data is not None:
        entry["summary"] = summarize_conversation(data)
        all_key_paths.update(collect_keys(data))
    manifest["conversations"].append(entry)

# keep one conversation fixture
unique_convs = []
seen = set()
for p in conv_files:
    h = sha256_file(p)
    if h in seen:
        continue
    seen.add(h)
    dest = OUT / "raw_conversation" / f"conversation_{h[:12]}.json"
    dest.write_bytes(p.read_bytes())
    unique_convs.append({"sha256": h, "bytes": p.stat().st_size, "fixture_path": str(dest.relative_to(OUT)), "sources": conv_hashes[h]})

manifest["unique_conversations"] = unique_convs
manifest["dedup"] = {
    "stream_files": len(stream_files),
    "stream_unique_content": len(content_hashes),
    "conversation_files": len(conv_files),
    "conversation_unique_content": len(conv_hashes),
    "conversation_all_identical": len(conv_hashes) == 1 and len(conv_files) == 3,
}

# Unified schema document
schema = {
    "name": "crcp.chatgpt_desktop.v1",
    "description": "Normalized ChatGPT Desktop fixtures: stream traces (UI-layer metadata only) + conversation exports (full text).",
    "components": {
        "StreamSnapshot": {
            "purpose": "Progressive UI streaming snapshot; typically NO message text, only hashes/lengths/directives/metadata.",
            "identity": ["sha256", "bytes"],
            "observed_top_level": unique_streams[0]["summary"].get("top_level_keys") if unique_streams else None,
            "observed_event_lists": unique_streams[-1]["summary"].get("event_lists") if unique_streams else None,
            "content_profile": {
                "expects_message_text": False,
                "hash_like_dominant": True if unique_streams and unique_streams[-1]["summary"].get("hash_like_strings",0) >= unique_streams[-1]["summary"].get("text_like_strings",0) else False,
            }
        },
        "ConversationExport": {
            "purpose": "Full conversation export with real message text and mapping tree.",
            "identity": ["sha256", "conversation_id_or_id"],
            "observed": unique_convs[0] if unique_convs else None,
            "content_profile": {"expects_message_text": True}
        },
        "FixtureBundle": {
            "fields": {
                "schema_version": "string",
                "generated_at": "iso8601",
                "unique_stream_snapshots": "StreamSnapshot[] ordered by bytes ascending",
                "unique_conversations": "ConversationExport[]",
                "dedup": "object",
            }
        }
    },
    "key_paths_top_50": all_key_paths.most_common(50),
}
manifest["unified_schema"] = schema

# human schema markdown
schema_md = f"""# ChatGPT Desktop Fixture Schema v1

Generated: {manifest['generated_at']}

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
- Unique snapshots: **{len(unique_streams)}** from **{len(stream_files)}** files.
- Progressive by size: **{manifest['stream_progressive']['is_progressive_by_size']}**

### Unique snapshot ladder
"""
for i,u in enumerate(unique_streams):
    hl = u['summary'].get('hash_like_strings')
    tl = u['summary'].get('text_like_strings')
    schema_md += f"- snap_{i:03d}: bytes={u['bytes']} sha256={u['sha256'][:16]}… hash_like={hl} text_like={tl} file={u['example_name']}\n"

schema_md += f"""
## ConversationExport (content)

- Full export for conversation family `6a5d2b66-a160-8327-9b06-baca0caf1584`.
- Files on disk: **{len(conv_files)}**; unique content: **{len(conv_hashes)}**.
- All identical: **{manifest['dedup']['conversation_all_identical']}**
"""
if unique_convs:
    # load summary from first conv entry
    csum = next((c['summary'] for c in manifest['conversations'] if c['sha256']==unique_convs[0]['sha256']), {})
    schema_md += f"""
### Content stats (deduped export)
- mapping_nodes: {csum.get('mapping_nodes')}
- roles: {csum.get('roles')}
- content_types: {csum.get('content_types')}
- total_text_chars: {csum.get('total_text_chars')}
- has_real_text: {csum.get('has_real_text')}
"""

schema_md += """
## Ingestion rule for CRCP bus

1. Prefer **ConversationExport** for payload text / research packs.
2. Use **StreamSnapshot** series only for protocol/schema regression and UI event taxonomy.
3. Drop-folder path: place new exports under `inbox/chatgpt/` → normalizer produces bus envelopes with `payload_ref` pointing at conversation fixture, optional `stream_trace_ref` for progressive meta.
"""

(OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
(OUT / "SCHEMA.md").write_text(schema_md, encoding="utf-8")
print("OUT", OUT)
print("stream_files", len(stream_files), "unique_streams", len(unique_streams))
print("conv_files", len(conv_files), "unique_convs", len(conv_hashes))
print("SUCCESS:fixtures")
