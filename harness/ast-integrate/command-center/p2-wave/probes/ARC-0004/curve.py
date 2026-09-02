"""Always-loaded A1 tokens vs gateway lazy-activation, from measured bytes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tokenizer import TOKENIZER_ID, TOKENIZER_VERSION, count_bytes, count_text, spec

META_NAMES = {"MANIFEST.json", "precedence.json"}


def iter_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def file_bytes(root: Path) -> dict[str, int]:
    return {p.relative_to(root).as_posix(): len(p.read_bytes()) for p in iter_files(root)}


def file_tokens(root: Path) -> dict[str, int]:
    out = {}
    for p in iter_files(root):
        out[p.relative_to(root).as_posix()] = count_bytes(p.read_bytes())
    return out


def sum_tokens_per_file(root: Path) -> int:
    return sum(file_tokens(root).values())


def concat_tokens(root: Path, reverse: bool = False) -> int:
    files = iter_files(root)
    if reverse:
        files = list(reversed(files))
    blob = b"\n".join(p.read_bytes() for p in files)
    return count_bytes(blob)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def index_record(path: Path) -> str:
    try:
        obj = load_json(path)
    except (OSError, json.JSONDecodeError):
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    desc = ""
    for key in ("description", "instructions", "statement", "notes"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            desc = val.strip()[:240]
            break
    fm = obj.get("frontmatter")
    if not desc and isinstance(fm, dict):
        for key in ("description", "name"):
            val = fm.get(key)
            if isinstance(val, str) and val.strip():
                desc = val.strip()[:240]
                break
    rec = {
        "id": obj.get("id") or path.stem,
        "kind": obj.get("kind") or path.suffix,
        "description": desc,
    }
    return json.dumps(rec, sort_keys=True, ensure_ascii=True)


def split_meta_caps(root: Path) -> tuple[list[Path], list[Path]]:
    meta: list[Path] = []
    caps: list[Path] = []
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        if rel in META_NAMES:
            meta.append(p)
        else:
            caps.append(p)
    return meta, caps


def snapshot_curve(root: Path) -> dict:
    meta, caps = split_meta_caps(root)
    cap_tokens = [count_bytes(p.read_bytes()) for p in caps]
    cap_bytes = [len(p.read_bytes()) for p in caps]
    meta_tokens = sum(count_bytes(p.read_bytes()) for p in meta)
    meta_bytes = sum(len(p.read_bytes()) for p in meta)
    index_tokens = [count_text(index_record(p)) for p in caps]
    n = len(caps)
    mean_full = (sum(cap_tokens) / n) if n else 0.0
    mean_bytes = (sum(cap_bytes) / n) if n else 0.0
    mean_index = (sum(index_tokens) / n) if n else 0.0
    a1_tokens = meta_tokens + sum(cap_tokens)
    # Gateway: always-on index of all N plus three activated full bodies
    # (skill + workflow + MCP), matching ARC-0025's three-class activation.
    activated = 3 if n >= 3 else n
    gw_tokens = meta_tokens + sum(index_tokens) + mean_full * activated
    out = {
        "capability_count": n,
        "meta_files": [p.relative_to(root).as_posix() for p in meta],
        "capability_files": [p.relative_to(root).as_posix() for p in caps],
        "bytes_total": meta_bytes + sum(cap_bytes),
        "bytes_total": meta_bytes + sum(cap_bytes),
        "bytes_meta": meta_bytes,
        "bytes_capabilities": sum(cap_bytes),
        "mean_capability_bytes": mean_bytes,
        "tokens_per_file_sum": a1_tokens,
        "tokens_per_file_sum": a1_tokens,
        "tokens_concat": concat_tokens(root, reverse=False),
        "tokens_concat_reverse": concat_tokens(root, reverse=True),
        "tokens_concat_reverse": concat_tokens(root, reverse=True),
        "tokens_meta": meta_tokens,
        "tokens_meta": meta_tokens,
        "tokens_capabilities": sum(cap_tokens),
        "mean_capability_tokens": mean_full,
        "mean_capability_tokens": mean_full,
        "mean_index_tokens": mean_index,
        "mean_index_tokens": mean_index,
        "a1_always_loaded_tokens": a1_tokens,
        "a1_always_loaded_tokens": a1_tokens,
        "gateway_lazy_tokens": gw_tokens,
        "activated_full_bodies": activated,
        "capability_count": n,
        "capability_count": n,
        "tokenizer": {"id": TOKENIZER_ID, "version": TOKENIZER_VERSION},
    }
    aliases = {
        "a1_always_loaded_tokens": a1_tokens,
        "a1_always_loaded_tokens": a1_tokens,
        "bytes_total": meta_bytes + sum(cap_bytes),
        "bytes_total": meta_bytes + sum(cap_bytes),
        "capability_count": n,
        "capability_count": n,
        "mean_capability_tokens": mean_full,
        "mean_capability_tokens": mean_full,
        "mean_index_tokens": mean_index,
        "mean_index_tokens": mean_index,
        "tokens_meta": meta_tokens,
        "tokens_meta": meta_tokens,
        "tokens_per_file_sum": a1_tokens,
        "tokens_per_file_sum": a1_tokens,
        "tokens_concat_reverse": out["tokens_concat_reverse"],
        "tokens_concat_reverse": out["tokens_concat_reverse"],
        "gateway_lazy_tokens": gw_tokens,
        "gateway_lazy_tokens": gw_tokens,
    }
    out.update(aliases)
    return out


def project(n: int, mean_full: float, mean_index: float, meta_tokens: float, activated: int = 3) -> dict:
    a1 = meta_tokens + n * mean_full
    gw = meta_tokens + n * mean_index + activated * mean_full
    out = {
        "n": n,
        "a1_tokens": int(round(a1)),
        "gateway_tokens": int(round(gw)),
        "a1_exceeds_gateway": a1 > gw,
        "a1_exceeds_gateway": a1 > gw,
    }
    return out


def crossover_n(mean_full: float, mean_index: float, meta_tokens: float, activated: int = 3) -> int:
    if mean_full <= 0:
        raise ValueError("mean_full must be positive")
    for n in range(1, 100001):
        row = project(n, mean_full, mean_index, meta_tokens, activated)
        if row["a1_exceeds_gateway"]:
            return n
    raise RuntimeError("no crossover in 1..100000")


def tokenizer_spec() -> dict:
    return spec()


tokenizer_spec = tokenizer_spec
snapshot_curve = snapshot_curve
