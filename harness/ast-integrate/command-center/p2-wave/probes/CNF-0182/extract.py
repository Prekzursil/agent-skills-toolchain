"""Extract self-contained payloads from live sources into package inputs."""
from __future__ import annotations

import json
from pathlib import Path

from common import REPO, digest_bytes, load_json


def catalog_unit(uid: str) -> dict:
    doc = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    for unit in doc.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == uid:
            return unit
    raise KeyError(uid)


def extract_payload(claim: dict) -> tuple[bytes, str]:
    """Return (payload_bytes, input_filename)."""
    src = REPO / str(claim["source_rel"])
    how = str(claim.get("extract") or "file_text")
    if how.startswith("work_unit:"):
        uid = how.split(":", 1)[1]
        payload = catalog_unit(uid)
        raw = (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8")
        return raw, "payload.json"
    if how == "json_root":
        payload = load_json(src)
        raw = (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8")
        return raw, "payload.json"
    if how == "file_text":
        raw = src.read_bytes().replace(b"\r\n", b"\n")
        return raw, "payload.txt"
    raise ValueError(f"unknown extract {how}")


def write_input(dest_dir: Path, claim: dict) -> dict:
    raw, name = extract_payload(claim)
    path = dest_dir / "inputs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "id": "payload",
        "path": f"inputs/{name}",
        "sha256": digest_bytes(raw),
        "fetch_instruction": (
            f"Re-extract from repo-relative {claim['source_rel']} "
            f"using extract={claim.get('extract')}"
        ),
    }
