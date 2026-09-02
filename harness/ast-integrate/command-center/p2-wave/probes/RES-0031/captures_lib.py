"""Load pinned RES-0031 captures and re-hash them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_metas() -> list[dict]:
    rows = []
    for meta_path in sorted(CAP.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict) or not meta.get("id"):
            raise SystemExit(f"bad meta {meta_path}")
        rel = str(meta.get("path") or "").replace("\\", "/")
        blob = REPO / rel if rel else None
        if blob is None or not blob.is_file():
            stem = meta_path.name[: -len(".meta.json")]
            cands = [
                p
                for p in CAP.glob(stem + ".*")
                if not p.name.endswith(".meta.json") and p.is_file()
            ]
            if not cands:
                raise SystemExit(f"missing blob for {meta['id']}")
            blob = cands[0]
        raw = blob.read_bytes()
        live = digest_bytes(raw)
        recorded = str(meta.get("sha256") or "")
        if recorded and recorded != live:
            raise SystemExit(
                f"capture sha mismatch {meta['id']}: recorded={recorded} live={live}"
            )
        meta = dict(meta)
        meta["_blob"] = blob
        meta["_text"] = raw.decode("utf-8", errors="replace")
        meta["_live_sha256"] = live
        rows.append(meta)
    if len(rows) < 20:
        raise SystemExit(f"too few captures: {len(rows)}")
    return rows


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {str(r["id"]): r for r in rows}


def concat_text(index: dict[str, dict], capture_ids: list[str]) -> str:
    parts = []
    for cid in capture_ids:
        row = index.get(cid)
        if row is None:
            raise SystemExit(f"unknown capture id {cid}")
        parts.append(row["_text"])
    return "\n".join(parts)
