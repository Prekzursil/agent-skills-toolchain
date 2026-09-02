#!/usr/bin/env python3
"""Isolate the owner's (owner, id <OWNER_DISCORD_ID>) messages from a DiscordChatExporter JSON.

Emits, into my_writing/Discord/:
  owner_all.txt          every message, timestamped — the complete record
  owner_substantial.txt  only messages >= MIN_CHARS — the actual WRITING (this is a my_writing corpus)
  owner.jsonl            structured (ts, len, content) for downstream tooling
System messages, calls, and pure-attachment/empty messages are dropped from the writing views.
"""

import glob
import json
import os
import re

# DiscordChatExporter emits "2017-12-18T12:06:25.714+03:00" -- an optional
# fractional part followed by "Z" or a signed HH:MM offset.
_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def tz_of(raw_ts):
    """Return the UTC offset carried by a Discord timestamp, or None.

    Kept separate from `ts` so the offset survives without changing the existing
    `ts` bytes. Never raises; a missing or unrecognised suffix yields None.
    """
    match = _TZ_SUFFIX.search(raw_ts or "")
    return match.group(1) if match else None


OWNER_ID = "<OWNER_DISCORD_ID>"
OWNER_NAME = "owner"
MIN_CHARS = 150  # the "long posts, not short thank-you" bar the owner set for Facebook, applied here too
DISCORD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Discord")


def main():
    sources = glob.glob(os.path.join(DISCORD_DIR, "*.json"))
    all_msgs, subst, records = [], [], []
    total = 0
    for src in sources:
        d = json.load(open(src, encoding="utf-8"))
        for m in d.get("messages", []):
            a = m.get("author", {})
            if a.get("id") != OWNER_ID and a.get("name") != OWNER_NAME:
                continue
            total += 1
            content = (m.get("content") or "").strip()
            if not content:
                continue  # attachment-only / sticker / empty — not writing
            if m.get("type") not in (None, "Default", "Reply", 0, 19):
                continue  # skip system/call messages
            raw_ts = m.get("timestamp") or ""
            ts = raw_ts[:19]
            # B0-ADV: the [:19] slice DISCARDS the UTC offset, and the offset is not
            # a constant -- the real control export carries BOTH +02:00 (58,122 msgs)
            # and +03:00 (157,220 msgs) because Romania observes DST. Truncating it
            # makes every Discord ts naive local wall-clock while isolate_facebook.py
            # renders UTC (isolate_facebook.py:861), so a merged corpus is mis-ordered
            # by up to 3h and 58k messages are shifted 1h against the other 157k.
            # `ts` is left byte-identical (sibling units pin the .txt outputs and
            # build_corpus.py:154 pins a .jsonl LINE NUMBER); the offset is preserved
            # additively so the information is no longer destroyed at the source.
            tz_offset = tz_of(raw_ts)
            line = f"[{ts}] {content}"
            all_msgs.append(line)
            records.append(
                {
                    "ts": ts,
                    "tz_offset": tz_offset,
                    "len": len(content),
                    "content": content,
                }
            )
            if len(content) >= MIN_CHARS:
                subst.append(line)

    out_all = os.path.join(DISCORD_DIR, "owner_all.txt")
    out_sub = os.path.join(DISCORD_DIR, "owner_substantial.txt")
    out_jsonl = os.path.join(DISCORD_DIR, "owner.jsonl")

    with open(out_all, "w", encoding="utf-8") as f:
        f.write("\n".join(all_msgs))
    with open(out_sub, "w", encoding="utf-8") as f:
        f.write("\n\n".join(subst))
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    subst_words = sum(len(s.split()) for s in subst)
    print(f"  owner messages total: {total}")
    print(f"  with text content:    {len(all_msgs)}")
    print(
        f"  substantial (>={MIN_CHARS} chars): {len(subst)}  (~{subst_words:,} words of writing)"
    )
    print(f"  -> {out_all}")
    print(f"  -> {out_sub}")
    print(f"  -> {out_jsonl}")


if __name__ == "__main__":
    main()
