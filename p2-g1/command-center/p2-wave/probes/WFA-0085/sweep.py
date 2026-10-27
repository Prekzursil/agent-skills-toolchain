"""Incremental discovery sweep with durable per-source checkpoints."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from identity import content_hash  # noqa: E402
from registry import empty_store, mark_checkpoint, merge_source, stable_ids  # noqa: E402
from store import atomic_write_json, load_json, registry_path  # noqa: E402


def load_migration(path: Path) -> dict[str, str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    aliases = doc.get("aliases") if isinstance(doc, dict) else None
    if not isinstance(aliases, dict):
        raise ValueError(f"migration map missing aliases: {path}")
    return {str(k): str(v) for k, v in aliases.items()}


def load_store(work: Path) -> dict[str, Any]:
    path = registry_path(work)
    if not path.is_file():
        return empty_store()
    return load_json(path)


def persist(work: Path, store: dict[str, Any]) -> None:
    atomic_write_json(registry_path(work), store)


def source_files(corpus: Path) -> list[Path]:
    return sorted(p for p in corpus.glob("*.json") if p.is_file())


def already_fresh(store: dict[str, Any], source_file: str, src: dict[str, Any]) -> bool:
    """Skip only when this source was checkpointed and its content hash is unchanged."""
    ck = store.get("checkpoint") or {}
    if source_file not in (ck.get("completed_sources") or []):
        return False
    ch = content_hash(src)
    for rec in store.get("records") or []:
        for p in rec.get("provenance") or []:
            if p.get("source_file") == source_file:
                return p.get("content_hash") == ch
    return False


def run_sweep(
    corpus: Path,
    work: Path,
    migration_map: dict[str, str],
    *,
    resume: bool = True,
) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    store = load_store(work) if resume else empty_store()
    n_new = 0
    for src_path in source_files(corpus):
        name = src_path.name
        src = json.loads(src_path.read_text(encoding="utf-8"))
        if already_fresh(store, name, src):
            n_done = len((store.get("checkpoint") or {}).get("completed_sources") or [])
            print(
                f"SKIP n={n_done} source={name} records={len(store['records'])}",
                flush=True,
            )
            continue
        merge_source(store, src, name, migration_map)
        mark_checkpoint(store, name)
        persist(work, store)
        n_new += 1
        n = len((store.get("checkpoint") or {}).get("completed_sources") or [])
        print(
            f"CHECKPOINT n={n} source={name} records={len(store['records'])} action_new={n_new}",
            flush=True,
        )
        hold = os.environ.get("WFA0085_HOLD_CHECKPOINT", "").strip()
        if hold.isdigit() and n == int(hold):
            time.sleep(2.0)
    persist(work, store)
    print(
        f"DONE sources={len((store.get('checkpoint') or {}).get('completed_sources') or [])} "
        f"records={len(store['records'])} ids={stable_ids(store)}",
        flush=True,
    )
    return store


def main() -> int:
    parser = argparse.ArgumentParser(description="WFA-0085 incremental discovery sweep")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--fresh", action="store_true", help="ignore checkpoint and registry")
    args = parser.parse_args()
    corpus = Path(args.corpus)
    work = Path(args.work)
    amap = load_migration(Path(args.map))
    run_sweep(corpus, work, amap, resume=not args.fresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
