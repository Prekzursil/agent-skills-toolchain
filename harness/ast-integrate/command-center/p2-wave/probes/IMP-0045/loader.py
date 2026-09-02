"""Shared loader + portability helpers for IMP-0045 probes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0045.json"
SENTINEL = "SUCCESS:IMP-0045"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))


def load_mod(name: str):
    path = PLUGIN / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"imp0045_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def worktree_sha(path: Path) -> str:
    """Hash raw working-tree bytes (the defective route)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_receipt() -> dict:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        raise FileNotFoundError(str(RECEIPT))
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        raise ValueError("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise ValueError(f"self-declared {doc.get('state')}")
    return doc
