"""Fixture registry builder for marketplace ranking research. RES-0060 / IMP-0118."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.marketplace.storage import digest_bytes, registry_dir


def _materialise(reg: Path) -> dict[str, Any]:
    blobs = reg / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    payloads = {
        "hello-skill@1.0.0": b"hello skill v1 payload\n",
        "hello-skill@1.1.0": b"Newer skill version payload\n",
    }
    packages = []
    for pid, body in payloads.items():
        digest = digest_bytes(body)
        rel = f"blobs/{digest}"
        (reg / rel).parent.mkdir(parents=True, exist_ok=True)
        (reg / rel).write_bytes(body)
        packages.append(
            {
                "id": pid,
                "name": pid.split("@")[0],
                "version": pid.split("@")[1],
                "blob": rel,
                "digest": digest,
                "bytes": len(body),
            }
        )
    index = {
        "schema": "marketplace-index/v1",
        "packages": packages,
        "documented": [],
        "inferred": [],
    }
    (reg / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def build(root: Path | str | None = None) -> dict[str, Any]:
    path = Path(root) if root else Path(__file__).resolve().parent / "fixture" / "registry"
    if (path / "tools" / "marketplace").is_dir() or (path / "command-center").is_dir():
        reg = registry_dir(path)
    else:
        reg = path
    return _materialise(reg)


def load_payloads(repo: Path) -> dict[str, bytes]:
    from tools.marketplace.storage import read_json

    root = registry_dir(Path(repo))
    index = read_json(root / "index.json")
    out: dict[str, bytes] = {}
    for pkg in index.get("packages") or []:
        out[pkg["id"]] = (root / pkg["blob"]).read_bytes()
    return out
