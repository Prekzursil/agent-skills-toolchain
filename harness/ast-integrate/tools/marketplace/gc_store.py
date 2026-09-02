"""On-disk blob store, index, lockfile, and deploy ledger for IMP-0125."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _blobs_dir(root: Path) -> Path:
    return Path(root) / "blobs"


def _index_path(root: Path) -> Path:
    return Path(root) / "index.json"


def _ledger_path(root: Path) -> Path:
    return Path(root) / "deploy-ledger.jsonl"


def _token_path(root: Path) -> Path:
    return Path(root) / "owner.token"


def _norm_hex(value: str) -> str:
    text = str(value).strip()
    if text.startswith("sha256:"):
        text = text[7:]
    return text.lower()


def set_owner_token(root: Path, token: str) -> None:
    path = _token_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")


def read_owner_token(root: Path) -> str:
    path = _token_path(root)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def put_blob(root: Path, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    dest = _blobs_dir(root)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / digest).write_bytes(data)
    return digest


def list_blob_hexes(root: Path) -> list[str]:
    dest = _blobs_dir(root)
    if not dest.is_dir():
        return []
    return sorted(p.name for p in dest.iterdir() if p.is_file())


def delete_blob(root: Path, digest_hex: str) -> None:
    path = _blobs_dir(root) / _norm_hex(digest_hex)
    if path.is_file():
        path.unlink()


def write_index(root: Path, entries: Iterable[dict[str, Any]]) -> None:
    _index_path(root).write_text(
        json.dumps(list(entries), indent=2) + "\n", encoding="utf-8"
    )


def write_lockfile(root: Path, name: str, entries: Iterable[dict[str, Any]]) -> None:
    path = Path(root) / name
    path.write_text(json.dumps(list(entries), indent=2) + "\n", encoding="utf-8")


def append_deploy_record(root: Path, record: dict[str, Any]) -> None:
    path = _ledger_path(root)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def load_index(root: Path) -> list[dict[str, Any]]:
    path = _index_path(root)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data) if isinstance(data, list) else []


def load_lockfiles(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(root).glob("*.lock.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item = dict(item)
                    item["_lockfile"] = path.name
                    rows.append(item)
    return rows


def load_deploy_records(root: Path) -> list[dict[str, Any]]:
    path = _ledger_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows
