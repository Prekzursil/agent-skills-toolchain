"""Shared paths and bytes helpers for CNF-0182."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PACKAGES = HERE / "packages"
FIXTURES = HERE / "fixtures"
SCHEMA_REL = "command-center/schema/replication-package.schema.json"
OUT_REL = "command-center/receipts/CNF-0182.json"
RUNTIME_ENV = "CNF0182_REPL_TOKEN"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def domain(doc: dict, key: str, default=None):
    """Read a domain field from the receipt root or report/extensions."""
    if isinstance(doc, dict) and key in doc:
        return doc[key]
    report = doc.get("report") if isinstance(doc, dict) else None
    if isinstance(report, dict) and key in report:
        return report[key]
    ext = doc.get("extensions") if isinstance(doc, dict) else None
    if isinstance(ext, dict) and key in ext:
        return ext[key]
    return default
