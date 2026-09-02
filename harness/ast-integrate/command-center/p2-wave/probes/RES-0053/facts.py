#!/usr/bin/env python3
"""Parse RES-0053 capture bytes into facts. No installed-client verdicts here.

Probe 2 re-derives those verdicts from phrases in the same bytes with its own
oracle so emit's table cannot self-certify.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
REPO = HERE.parents[3]


def body_path(cid: str) -> Path:
    return CAP / f"{cid}.body"


def meta_path(cid: str) -> Path:
    return CAP / f"{cid}.meta.json"


def load_meta(cid: str) -> dict:
    return json.loads(meta_path(cid).read_text(encoding="utf-8"))


def load_bytes(cid: str) -> bytes:
    return body_path(cid).read_bytes()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text(cid: str) -> str:
    return load_bytes(cid).decode("utf-8", errors="replace")


def rail(cid: str, kind: str) -> dict:
    meta = load_meta(cid)
    raw = load_bytes(cid)
    digest = sha256_bytes(raw)
    if digest != meta.get("sha256"):
        raise ValueError(f"sidecar sha256 stale for {cid}")
    return {
        "id": cid,
        "kind": kind,
        "permalink": meta["permalink"],
        "resolved_url": meta.get("resolved_url") or meta["permalink"],
        "fetch_timestamp": meta["fetch_timestamp"],
        "http_status": int(meta["http_status"]),
        "sha256": digest,
        "bytes": len(raw),
        "captured_path": (
            "command-center/p2-wave/probes/RES-0053/captures/" + cid + ".body"
        ),
        "role": meta.get("role"),
    }


def npm_flatmap() -> dict:
    doc = json.loads(text("npm-api-unpublished-flatmap-stream"))
    versions = doc.get("versions") or {}
    latest = (doc.get("dist-tags") or {}).get("latest")
    return {
        "name": doc.get("name"),
        "description": doc.get("description"),
        "latest": latest,
        "latest_is_security_holder": latest == "0.0.1-security",
        "n_versions": len(versions),
        "readme_head": (doc.get("readme") or "")[:180],
    }


def npm_event_stream() -> dict:
    doc = json.loads(text("npm-api-event-stream"))
    versions = doc.get("versions") or {}
    time = doc.get("time") or {}
    return {
        "latest": (doc.get("dist-tags") or {}).get("latest"),
        "has_3_3_6_in_versions": "3.3.6" in versions,
        "time_3_3_6": time.get("3.3.6"),
        "n_versions": len(versions),
    }


def pypi_urllib3_yanked() -> list[dict]:
    doc = json.loads(text("pypi-api-simple-urllib3"))
    out = []
    for item in doc.get("files") or []:
        yanked = item.get("yanked")
        if yanked in (False, None, ""):
            continue
        out.append(
            {
                "filename": item.get("filename"),
                "yanked": yanked,
                "url": item.get("url"),
            }
        )
    return out


def crates_futures_020() -> dict:
    doc = json.loads(text("crates-api-futures-0-2-0"))
    ver = doc.get("version") or {}
    return {
        "crate": ver.get("crate"),
        "num": ver.get("num"),
        "yanked": ver.get("yanked"),
        "dl_path": ver.get("dl_path"),
    }


def vscode_material() -> dict:
    doc = json.loads(text("vscode-api-material-theme"))
    results = doc.get("results") or []
    ext = None
    if results and (results[0].get("extensions") or []):
        ext = results[0]["extensions"][0]
    flags = (ext or {}).get("flags")
    return {
        "found": ext is not None,
        "display_name": (ext or {}).get("displayName"),
        "flags": flags,
        "extension_name": (ext or {}).get("extensionName"),
        "has_revoked_field": isinstance(ext, dict) and (
            "revoked" in ext or "blocked" in ext or "blocklisted" in ext
        ),
        "public": isinstance(flags, str) and "public" in flags,
    }


def jetbrains_python() -> dict:
    doc = json.loads(text("jetbrains-api-python-plugin"))
    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "isHidden": doc.get("isHidden"),
        "isBlocked": doc.get("isBlocked"),
        "has_hidden_field": "isHidden" in doc,
        "has_blocked_field": "isBlocked" in doc,
    }


def contains(cid: str, needle: str) -> bool:
    hay = " ".join(text(cid).split())
    want = " ".join(needle.split())
    return want in hay
