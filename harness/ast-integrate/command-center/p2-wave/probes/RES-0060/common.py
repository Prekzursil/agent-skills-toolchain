"""Shared capture loaders for RES-0060 probes (no ranking labels)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/research/RES-0060.json"
CAPTURES = HERE / "captures"
INDEX = CAPTURES / "_index.json"
SENTINEL = (
    "SUCCESS:RES-0060 in the receipt AND a ranking-factor list split "
    "documented-versus-inferred with the undocumented proportion stated"
)
POPULARITY_KEYS = {
    "installs",
    "install_count",
    "installCount",
    "downloads",
    "download_count",
    "downloadCount",
    "popularity",
    "stars",
    "star_count",
}


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_index() -> list[dict[str, Any]]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def capture_row(cid: str) -> dict[str, Any]:
    for row in load_index():
        if row.get("id") == cid:
            return row
    raise KeyError(cid)


def capture_path(cid: str) -> Path:
    row = capture_row(cid)
    rel = str(row["path"]).replace("\\", "/")
    return REPO / rel


def capture_text(cid: str) -> str:
    return capture_path(cid).read_text(encoding="utf-8", errors="replace")


def vscode_ranked_ids(cid: str, n: int = 8) -> list[str]:
    data = json.loads(capture_path(cid).read_text(encoding="utf-8"))
    exts = data["results"][0]["extensions"]
    out: list[str] = []
    for e in exts[:n]:
        pub = (e.get("publisher") or {}).get("publisherName") or ""
        out.append(f"{pub}.{e.get('extensionName')}")
    return out


def vscode_installs(cid: str, n: int = 8) -> list[int]:
    data = json.loads(capture_path(cid).read_text(encoding="utf-8"))
    vals: list[int] = []
    for e in data["results"][0]["extensions"][:n]:
        stats = {s["statisticName"]: s["value"] for s in e.get("statistics") or []}
        vals.append(int(stats.get("install") or 0))
    return vals


def catalog_unit(uid: str) -> dict[str, Any]:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def nested_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k))
            keys |= nested_keys(v)
    elif isinstance(obj, list):
        for item in obj[:12]:
            keys |= nested_keys(item)
    return keys
