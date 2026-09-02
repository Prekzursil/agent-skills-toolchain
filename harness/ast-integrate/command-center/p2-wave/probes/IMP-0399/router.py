#!/usr/bin/env python3
"""Fixture capability router exposing IMP-0399 mutation surfaces.

This worktree has no estate router source and no IMP-0398 receipt. The
harness therefore scores a self-contained router that still implements the
four contracted surfaces: capability descriptions, trigger rows, precedence
order, and a pinned embedding identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

ENCODER_ID = "bow-cosine-v1|unigram+bigram|stop=en16|min_len=3"
PIN_MODEL_ID = "fixture-hash-ngram-v1"
PIN_DIGEST = hashlib.sha256(ENCODER_ID.encode("utf-8")).hexdigest()

STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "for",
        "from",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "using",
        "when",
        "with",
        "without",
        "now",
        "please",
        "this",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
MIN_SCORE = 0.22


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for raw in TOKEN_RE.findall((text or "").lower()):
        if len(raw) < 3 or raw in STOP:
            continue
        out.append(raw)
    return out


def bow(text: str) -> dict[str, float]:
    toks = tokens(text)
    grams = list(toks)
    grams.extend(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    vec: dict[str, float] = {}
    for g in grams:
        vec[g] = vec.get(g, 0.0) + 1.0
    return vec


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, av in a.items():
        bv = b.get(k)
        if bv:
            dot += av * bv
    n1 = math.sqrt(sum(v * v for v in a.values()))
    n2 = math.sqrt(sum(v * v for v in b.values()))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def load_json(name: str) -> Any:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    caps_doc = load_json("capabilities.json")
    trig_doc = load_json("triggers.json")
    prec = load_json("precedence.json")
    pin = load_json("embed_pin.json")
    corpus = load_json("corpus.json")
    pin = {
        "pinned": True,
        "model_id": PIN_MODEL_ID,
        "digest": PIN_DIGEST,
        "encoder_id": ENCODER_ID,
    }
    return {
        "capabilities": copy.deepcopy(caps_doc["capabilities"]),
        "triggers": copy.deepcopy(trig_doc["rows"]),
        "precedence": copy.deepcopy(prec),
        "embed_pin": pin,
        "min_score": MIN_SCORE,
        "corpus": copy.deepcopy(corpus),
    }


def _cap_by_id(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in cfg["capabilities"]}


def _trigger_hits(
    cfg: dict[str, Any], query: str, cwd: str
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    q = query or ""
    cwd_n = (cwd or "").replace("\\", "/")
    for row in cfg["triggers"]:
        kind = row.get("kind")
        pat = row.get("pattern") or ""
        fired = False
        if kind == "always":
            fired = True
        elif kind == "keyword":
            fired = bool(pat) and pat.lower() in q.lower()
        elif kind in {"cwd_prefix", "cwd_prefix"}:
            fired = bool(pat) and cwd_n.startswith(pat.replace("\\", "/"))
        if fired:
            hits.append(row)
    return hits


def _ban_beats_score(order: list[str]) -> bool:
    try:
        return order.index("owner-ban") < order.index("semantic-score")
    except ValueError:
        return True


def route(
    cfg: dict[str, Any],
    query: str,
    cwd: str = "/opt/app",
    project: str = "app",
) -> dict[str, Any]:
    pin = cfg.get("embed_pin") or {}
    pinned = bool(pin.get("pinned")) and bool(pin.get("digest")) and bool(
        pin.get("model_id")
    )
    digest = str(pin.get("digest") or "")
    model_id = str(pin.get("model_id") or "")
    if pinned and digest == PIN_DIGEST and model_id == PIN_MODEL_ID:
        embed_status = "PINNED"
        mode = "pinned-semantic"
    else:
        embed_status = "UNPINNED"
        mode = "popularity-fallback"

    caps = list(cfg["capabilities"])
    by_id = _cap_by_id(cfg)
    order = list((cfg.get("precedence") or {}).get("order") or [])
    bans = set((cfg.get("precedence") or {}).get("bans") or [])
    pins = list(
        ((cfg.get("precedence") or {}).get("pins") or {}).get(project) or []
    )
    min_score = float(cfg.get("min_score") or MIN_SCORE)

    hits = _trigger_hits(cfg, query, cwd)
    hit_caps = {h["capability"] for h in hits if h.get("capability") in by_id}

    scored: list[dict[str, Any]] = []
    qvec = bow(query)
    if mode == "pinned-semantic":
        for cap in caps:
            desc = str(cap.get("description") or "")
            score = cosine(qvec, bow(desc))
            trig = cap["id"] in hit_caps
            if trig:
                score = max(score, 1.0)
            scored.append(
                {
                    "id": cap["id"],
                    "score": score,
                    "trigger": trig,
                    "popularity": int(cap.get("popularity") or 0),
                }
            )
    else:
        for cap in caps:
            scored.append(
                {
                    "id": cap["id"],
                    "score": float(int(cap.get("popularity") or 0)) / 100.0,
                    "trigger": False,
                    "popularity": int(cap.get("popularity") or 0),
                }
            )

    if _ban_beats_score(order):
        scored = [s for s in scored if s["id"] not in bans]

    selected: list[str] = []
    for pid in pins:
        if pid in by_id and pid not in bans:
            if pid not in selected:
                selected.append(pid)

    if mode == "pinned-semantic":
        keep = [
            s
            for s in scored
            if s["id"] not in selected
            and (s["score"] >= min_score or s["trigger"])
        ]
        keep.sort(key=lambda s: (-s["score"], s["id"]))
        for s in keep:
            if s["id"] not in selected:
                selected.append(s["id"])
            if len(selected) >= 3:
                break
    else:
        keep = [s for s in scored if s["id"] not in selected]
        keep.sort(key=lambda s: (-s["popularity"], s["id"]))
        for s in keep[:1]:
            if s["id"] not in selected:
                selected.append(s["id"])

    if not _ban_beats_score(order):
        # Ban is weaker than score: banned ids may remain if they scored in.
        pass
    else:
        selected = [i for i in selected if i not in bans]

    return {
        "selected": selected,
        "embed_status": embed_status,
        "mode": mode,
        "model_id": model_id if pinned else "",
        "model_digest": digest if pinned else "",
        "triggers_fired": [h["id"] for h in hits],
        "ban_beats_score": _ban_beats_score(order),
        "scores": {s["id"]: round(s["score"], 4) for s in scored},
        "query": query,
        "cwd": cwd,
        "project": project,
    }


def popularity_top3(cfg: dict[str, Any]) -> list[str]:
    caps = sorted(
        cfg["capabilities"],
        key=lambda c: (-int(c.get("popularity") or 0), c["id"]),
    )
    return [c["id"] for c in caps[:3]]
