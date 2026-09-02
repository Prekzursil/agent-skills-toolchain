#!/usr/bin/env python3
"""Deterministic-when-pinned workflow runner for CNF-0074 replay.

Stages actually scan a corpus, optionally sample / stamp / leak a path, then
write a canonical JSON artifact. A content cache keys on input digest so a
one-input mutation cannot be masked. A broken id-only cache is the known-broken
detector-control fixture.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fixtures" / "corpus"
WF_DIR = HERE / "fixtures" / "workflows"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def scan_corpus(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes().replace(b"\r\n", b"\n")
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_bytes(data),
                "size": len(data),
            }
        )
    return files


def corpus_digest(root: Path) -> str:
    return sha256_bytes(canonical(scan_corpus(root)))


class ArtifactCache:
    """In-memory artifact cache.

    content: key = (workflow id, corpus digest, seed, routing pin, stages).
    broken-id-only: key = workflow id (known-broken fixture).
    off: never hits.
    """

    def __init__(self, mode: str = "content") -> None:
        if mode not in {"content", "broken-id-only", "off"}:
            raise ValueError(f"bad cache mode {mode}")
        self.mode = mode
        self._store: dict[str, bytes] = {}
        self.hits = 0
        self.misses = 0

    def key(self, wf: dict[str, Any], corpus: Path) -> str:
        if self.mode == "broken-id-only":
            return f"id-only:{wf['id']}"
        if self.mode == "off":
            return f"off:{time.time_ns()}:{os.urandom(8).hex()}"
        payload = {
            "id": wf["id"],
            "seed": wf.get("seed"),
            "routing_pin": wf.get("routing_pin"),
            "stages": wf.get("stages"),
            "corpus": corpus_digest(corpus),
        }
        return sha256_bytes(canonical(payload))

    def get(self, k: str) -> bytes | None:
        hit = self._store.get(k)
        if hit is None:
            self.misses += 1
            return None
        self.hits += 1
        return hit

    def put(self, k: str, raw: bytes) -> None:
        self._store[k] = raw


def _seeded_pick(files: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    if not files:
        raise ValueError("empty corpus")
    return files[int(seed) % len(files)]


def _unseeded_pick(files: list[dict[str, Any]]) -> dict[str, Any]:
    if not files:
        raise ValueError("empty corpus")
    n = time.time_ns() ^ int.from_bytes(os.urandom(8), "big")
    return files[n % len(files)]


def execute(wf: dict[str, Any], corpus: Path, run_dir: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    seed = wf.get("seed")
    pin = wf.get("routing_pin")
    files = scan_corpus(corpus)
    state: dict[str, Any] = {
        "workflow_id": wf["id"],
        "seed": seed,
        "routing_pin": pin,
        "claims_determinism": bool(wf.get("claims_determinism")),
        "candidates": files,
        "candidate_count": len(files),
        "stage_trace": [],
    }
    for stage in wf.get("stages") or []:
        kind = stage.get("kind")
        sid = stage.get("id") or kind
        if kind == "static-scan":
            state["candidates"] = files
            state["candidate_count"] = len(files)
        elif kind == "write-config":
            payload = {
                "candidates": state["candidates"],
                "seed": seed,
                "routing_pin": pin,
            }
            state["config_digest"] = sha256_bytes(canonical(payload))
        elif kind == "stamp-time":
            state["created_at"] = time.time_ns()
            state["stamped_at"] = f"ns:{state['created_at']}"
        elif kind == "seeded-sample":
            if seed is None:
                raise ValueError("seeded-sample requires seed")
            picked = _seeded_pick(state["candidates"], int(seed))
            state["chosen"] = picked["path"]
            state["chosen_sha256"] = picked["sha256"]
        elif kind == "unseeded-sample":
            picked = _unseeded_pick(state["candidates"])
            # Nonce is part of the semantic payload so two runs cannot collide
            # just because they happened to pick the same path.
            state["chosen"] = picked["path"]
            state["chosen_sha256"] = picked["sha256"]
            # Hex prefix so the value cannot be mistaken for a timestamp.
            state["sample_nonce"] = "nonce:" + (
                time.time_ns() ^ int.from_bytes(os.urandom(8), "big")
            ).to_bytes(8, "big").hex()
        elif kind == "embed-path":
            state["run_dir"] = str(run_dir.resolve())
            state["abs_path"] = str((run_dir / "artifact.json").resolve())
        else:
            raise ValueError(f"unknown stage kind {kind}")
        state["stage_trace"].append({"id": sid, "kind": kind})
    state["model_route"] = {"pin": pin, "resolved": f"{pin}|seed={seed}"}
    return state


def run_workflow(
    wf: dict[str, Any],
    corpus: Path,
    run_dir: Path,
    cache: ArtifactCache | None = None,
) -> dict[str, Any]:
    cache = cache or ArtifactCache(mode="off")
    key = cache.key(wf, corpus)
    cached = cache.get(key)
    if cached is not None:
        obj = json.loads(cached.decode("utf-8"))
        return {
            "object": obj,
            "bytes": cached,
            "sha256": sha256_bytes(cached),
            "cache_hit": True,
            "cache_key": key,
        }
    obj = execute(wf, corpus, run_dir)
    raw = canonical(obj)
    cache.put(key, raw)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "artifact.json").write_bytes(raw)
    return {
        "object": obj,
        "bytes": raw,
        "sha256": sha256_bytes(raw),
        "cache_hit": False,
        "cache_key": key,
    }


def load_workflow(name: str) -> dict[str, Any]:
    return json.loads((WF_DIR / name).read_text(encoding="utf-8"))


def all_workflows() -> list[dict[str, Any]]:
    names = [
        "wf.catalog-class.discovery-only.json",
        "wf.seeded-stable.json",
        "wf.timestamp-wallclock.json",
        "wf.overclaim-unseeded-sample.json",
        "wf.path-leaking.json",
    ]
    return [load_workflow(n) for n in names]


def copy_corpus(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if path.is_dir():
            (dest / path.relative_to(src)).mkdir(parents=True, exist_ok=True)
            continue
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def mutate_one_file(corpus: Path, rel: str, payload: bytes) -> None:
    path = corpus / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    path.write_bytes(payload.replace(b"\r\n", b"\n"))
