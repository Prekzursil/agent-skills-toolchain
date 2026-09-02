#!/usr/bin/env python3
"""Load capture index and verify on-disk sha256 for RES-0122 rails."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
INDEX = CAPTURES / "_index.json"
REQUIRED_RAIL_KEYS = (
    "kind",
    "permalink",
    "fetch_timestamp",
    "http_status",
    "sha256",
    "capture",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> dict[str, dict]:
    rows = json.loads(INDEX.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in rows:
        name = str(row["name"])
        path = CAPTURES / name
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        if digest != row["sha256"]:
            raise SystemExit(f"capture sha mismatch {name}")
        if int(row["http_status"]) != 200:
            raise SystemExit(f"capture not HTTP 200 {name}")
        rec = dict(row)
        rec["path"] = str(path)
        rec["live_sha256"] = digest
        rec["live_bytes"] = len(raw)
        out[name] = rec
    return out


def rail_from_index(index: dict[str, dict], name: str, kind: str) -> dict:
    rec = index[name]
    return {
        "kind": kind,
        "permalink": rec["permalink"],
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": int(rec["http_status"]),
        "sha256": rec["sha256"],
        "capture": name,
        "bytes": rec["bytes"],
        "content_type": rec.get("content_type") or rec.get("final_url"),
    }


def capture_text(name: str) -> str:
    return (CAPTURES / name).read_text(encoding="utf-8", errors="replace")


def assert_quote_in_capture(quote: str, capture: str) -> None:
    body = capture_text(capture)
    if quote not in body:
        raise SystemExit(f"clause quote not in {capture}: {quote[:80]!r}")


def check_rail(index: dict[str, dict], rail: dict) -> str | None:
    for key in REQUIRED_RAIL_KEYS:
        if key not in rail:
            return f"rail missing {key}"
    if rail["kind"] not in {"api", "prose"}:
        return f"bad rail kind {rail['kind']}"
    if int(rail["http_status"]) != 200:
        return f"rail http_status {rail['http_status']}"
    name = str(rail["capture"])
    rec = index.get(name)
    if rec is None:
        return f"unknown capture {name}"
    if str(rail["sha256"]) != rec["sha256"]:
        return f"rail sha256 != capture {name}"
    if str(rail["permalink"]) != rec["permalink"]:
        return f"rail permalink != capture {name}"
    if int(rail["http_status"]) != int(rec["http_status"]):
        return f"rail status != capture {name}"
    if not str(rail["fetch_timestamp"]).strip():
        return "empty fetch_timestamp"
    return None


load_index = load_index
rail_from_index = rail_from_index
assert_quote_in_capture = assert_quote_in_capture


def check_claim_two_rails(index: dict[str, dict], claim: dict) -> str | None:
    rails = claim.get("rails") or []
    if len(rails) < 2:
        return f"{claim.get('id')} has {len(rails)} rails"
    kinds = {r.get("kind") for r in rails}
    cid = str(claim.get("id") or "")
    if cid == "C-102B":
        if kinds != {"prose"}:
            return f"{cid} statute rails must both be prose, got {kinds}"
    elif kinds != {"api", "prose"}:
        return f"{cid} rails not api+prose: {kinds}"
    publishers = {str(r.get("permalink") or "").split("/")[2] for r in rails}
    if len(publishers) < 2:
        return f"{claim.get('id')} both rails same host {publishers}"
    for rail in rails:
        err = check_rail(index, rail)
        if err:
            return f"{claim.get('id')} {err}"
    return None
