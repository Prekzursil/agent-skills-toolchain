"""Deploy-ledger provenance walker (independent of index/lockfile scan)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gc_store import load_deploy_records


def _hex(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("sha256:"):
        text = text[7:]
    return text.lower()


class ProvenanceScan:
    def __init__(self, refs: dict[str, list[str]], dangling: list[dict[str, Any]]) -> None:
        self._refs = refs
        self.dangling = dangling

    def refs_for(self, digest_hex: str) -> list[str]:
        return list(self._refs.get(_hex(digest_hex), []))

    def all_hexes(self) -> set[str]:
        return set(self._refs)


def walk_deploy_provenance(root: Path) -> ProvenanceScan:
    refs: dict[str, list[str]] = {}
    dangling: list[dict[str, Any]] = []
    for rec in load_deploy_records(root):
        digest = _hex(rec.get("source_blob_sha") or rec.get("blob_digest"))
        live = rec.get("live_path")
        tag = "deploy-ledger.jsonl:source_blob_sha"
        if digest:
            refs.setdefault(digest, []).append(tag)
        if live and not Path(str(live)).exists():
            dangling.append(
                {
                    "live_path": str(live),
                    "source_blob_sha": rec.get("source_blob_sha"),
                    "source_path": rec.get("source_path"),
                }
            )
    return ProvenanceScan(refs, dangling)
