"""On-disk and temp-tree fixtures for TST-0148 shard-set probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
SHARD_IDS = ("SHARD-A", "SHARD-B", "SHARD-C", "SHARD-D")
MISSING_ID = "SHARD-C"
MANIFEST_NAME = "shard-manifest.json"


def shard_filename(shard_id: str) -> str:
    return f"{shard_id.lower()}.json"


def manifest_doc(set_id: str = "TST-0148-control-set") -> dict:
    return {
        "set_id": set_id,
        "shards": [{"id": sid, "path": shard_filename(sid)} for sid in SHARD_IDS],
    }


def shard_payload(shard_id: str) -> str:
    return json.dumps({"shard_id": shard_id, "payload": shard_id.lower()}, indent=2) + "\n"


def write_manifest(path: Path, set_id: str = "TST-0148-control-set") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest_doc(set_id), indent=2) + "\n", encoding="utf-8")
    return path


def write_shards(set_root: Path, ids: Iterable[str]) -> None:
    set_root.mkdir(parents=True, exist_ok=True)
    wanted = set(ids)
    for sid in SHARD_IDS:
        dest = set_root / shard_filename(sid)
        if sid in wanted:
            dest.write_text(shard_payload(sid), encoding="utf-8")
        elif dest.exists():
            dest.unlink()


def materialize_ondisk() -> dict[str, Path]:
    """Write the checked-in fixture trees used as supporting artifacts."""
    man = write_manifest(FIX / MANIFEST_NAME)
    complete = FIX / "complete"
    incomplete = FIX / "incomplete"
    write_shards(complete, SHARD_IDS)
    write_shards(incomplete, [s for s in SHARD_IDS if s != MISSING_ID])
    return {
        "manifest": man,
        "complete": complete,
        "incomplete": incomplete,
    }


def populate_tree(root: Path, *, omit: str | None = None) -> tuple[Path, Path]:
    """Build a live set under root. Returns (set_root, manifest_path)."""
    set_root = root / "shards"
    man = write_manifest(root / MANIFEST_NAME)
    ids = [s for s in SHARD_IDS if s != omit]
    write_shards(set_root, ids)
    return set_root, man
