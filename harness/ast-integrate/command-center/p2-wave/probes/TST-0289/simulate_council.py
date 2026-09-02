"""Deterministic scripted-persona council runtime for TST-0289.

Catalog input `tools/council/simulate.py` re-exports this module. Personas are
seeded state machines (priors + susceptibility), not live model calls.

Three protocol modes, matched on the same seed:

- identity_revealed: sequential speaking, names published, later seats observe
  earlier openings. High-status first speaker is seated first when asked.
- identity_concealed: blind independent first pass. Openings are written from
  each seat's prior with no observation and no identity/style/tool cues.
- ceremony_mask_only: same observation as revealed (so vectors match), but
  published names are masked. Style tokens and tool traces remain. This is the
  name-masking-is-ceremony control.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Iterable, Mapping, Sequence

MODE_REVEALED = "identity_revealed"
MODE_CONCEALED = "identity_concealed"
MODE_CEREMONY = "ceremony_mask_only"
KNOWN_MODES = {MODE_REVEALED, MODE_CONCEALED, MODE_CEREMONY}
NOISE_SIGMA = 0.012


class PersonaMissing(Exception):
    """Raised when a speak-order seat has no persona script (fail loud)."""

    def __init__(self, seat_id: str) -> None:
        self.seat_id = str(seat_id)
        super().__init__(f"persona-missing:{self.seat_id}")


def _renorm(xs: Sequence[float]) -> list[float]:
    vals = [max(1e-12, float(x)) for x in xs]
    total = sum(vals)
    if total <= 0.0:
        n = len(vals) or 1
        return [1.0 / n] * n
    return [v / total for v in vals]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _l2(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _euclid(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na = _l2(a)
    nb = _l2(b)
    if na < 1e-15 or nb < 1e-15:
        return 0.0
    return _dot(a, b) / (na * nb)


def mean_pairwise_distance(vectors: Sequence[Sequence[float]]) -> float:
    n = len(vectors)
    if n < 2:
        return 0.0
    acc = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            acc += _euclid(vectors[i], vectors[j])
            count += 1
    return acc / count if count else 0.0


def subsequent_pull_mean(tr: Mapping[str, Any]) -> float:
    rows = list(tr.get("openings_by_speak_order") or [])
    if len(rows) < 2:
        return 0.0
    first = list(rows[0]["vector"])
    pulls = [cosine(first, list(row["vector"])) for row in rows[1:]]
    return sum(pulls) / len(pulls)


def _perturb(prior: Sequence[float], rng: random.Random, sigma: float = NOISE_SIGMA) -> list[float]:
    noisy = [float(p) + rng.gauss(0.0, sigma) for p in prior]
    return _renorm(noisy)


def _status_mean(observed: Sequence[tuple[Sequence[float], float]]) -> list[float]:
    if not observed:
        return []
    dim = len(observed[0][0])
    weight = sum(float(w) for _, w in observed)
    if weight <= 0.0:
        weight = 1.0
    acc = [0.0] * dim
    for vec, w in observed:
        ww = float(w)
        for i, x in enumerate(vec):
            acc[i] += float(x) * ww
    return [x / weight for x in acc]


def _mix(prior: Sequence[float], target: Sequence[float], alpha: float) -> list[float]:
    w = min(1.0, max(0.0, float(alpha)))
    return _renorm([(1.0 - w) * float(p) + w * float(t) for p, t in zip(prior, target)])


def _argmax(vec: Sequence[float]) -> int:
    best_i = 0
    best_v = float(vec[0]) if vec else 0.0
    for i, x in enumerate(vec):
        fx = float(x)
        if fx > best_v:
            best_v = fx
            best_i = i
    return best_i


def _verdict(vectors: Sequence[Sequence[float]], labels: Sequence[str]) -> str:
    if not vectors:
        return str(labels[0]) if labels else "unknown"
    dim = len(labels)
    acc = [0.0] * dim
    for vec in vectors:
        for i in range(min(dim, len(vec))):
            acc[i] += float(vec[i])
    return str(labels[_argmax(acc)])


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _by_id(personas: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for p in personas:
        pid = str(p["id"])
        if pid in out:
            raise ValueError(f"duplicate persona id {pid}")
        out[pid] = p
    return out


def _speak_order(spec: Mapping[str, Any], seated: Mapping[str, Mapping[str, Any]]) -> list[str]:
    order = [str(s) for s in (spec.get("speak_order") or [])]
    if not order:
        order = list(seated.keys())
    missing = [sid for sid in order if sid not in seated]
    if missing:
        raise PersonaMissing(missing[0])
    mode = str(spec.get("mode") or "")
    if spec.get("high_status_first") and mode in {MODE_REVEALED, MODE_CEREMONY}:
        ranked = sorted(
            order,
            key=lambda sid: (-float(seated[sid].get("status_weight") or 0.0), sid),
        )
        head = ranked[0]
        if order[0] != head:
            order = [head] + [s for s in order if s != head]
    return order


def _opening_text(
    *,
    persona: Mapping[str, Any],
    published_name: str,
    vector: Sequence[float],
    mode: str,
    seed: int,
    labels: Sequence[str],
    seat_index: int,
) -> str:
    stance = str(labels[_argmax(vector)]) if labels else "unknown"
    weights = ",".join(f"{x:.6f}" for x in vector)
    draw = hashlib.sha256(f"{seed}|{persona['id']}|{mode}".encode("utf-8")).hexdigest()[:10]
    if mode == MODE_REVEALED:
        styles = " ".join(str(t) for t in (persona.get("style_tokens") or []))
        return (
            f"{published_name} ({persona.get('title')}) opening {styles} "
            f"stance={stance} weights=[{weights}] "
            f"tool://seat/{persona['id']}/open seed={seed} draw={draw}"
        )
    if mode == MODE_CEREMONY:
        styles = " ".join(str(t) for t in (persona.get("style_tokens") or []))
        return (
            f"{published_name} opening {styles} stance={stance} "
            f"weights=[{weights}] tool://seat/{persona['id']}/open "
            f"seed={seed} draw={draw}"
        )
    return (
        f"{published_name} independent opening stance={stance} "
        f"weights=[{weights}] seed={seed} draw={draw} seat-index={seat_index}"
    )


def run_council(
    spec: Mapping[str, Any],
    personas: Sequence[Mapping[str, Any]],
    seed: int,
) -> dict[str, Any]:
    mode = str(spec.get("mode") or "")
    if mode not in KNOWN_MODES:
        raise ValueError(f"unknown council mode {mode!r}")
    labels = [str(x) for x in (spec.get("labels") or ["merge", "revise", "escalate", "defer"])]
    seated = _by_id(personas)
    order = _speak_order(spec, seated)
    missing = [sid for sid in order if sid not in seated]
    if missing:
        raise PersonaMissing(missing[0])

    rng = random.Random(int(seed))
    priors = {sid: _perturb(list(seated[sid]["prior"]), rng) for sid in order}

    observe = mode != MODE_CONCEALED
    identity_published = mode == MODE_REVEALED
    blind_first_pass = mode == MODE_CONCEALED

    openings: list[dict[str, Any]] = []
    observed: list[tuple[list[float], float]] = []
    for idx, sid in enumerate(order):
        persona = seated[sid]
        prior = priors[sid]
        if observe and observed:
            target = _status_mean(observed)
            vector = _mix(prior, target, float(persona.get("alpha") or 0.0))
        else:
            vector = list(prior)
        if identity_published:
            published = str(persona.get("name") or sid)
        else:
            published = f"Seat-{idx + 1}"
        text = _opening_text(
            persona=persona,
            published_name=published,
            vector=vector,
            mode=mode,
            seed=int(seed),
            labels=labels,
            seat_index=idx,
        )
        row = {
            "seat_id": sid,
            "published_name": published,
            "real_name": str(persona.get("name") or ""),
            "text": text,
            "vector": vector,
            "speak_index": idx,
            "status_weight": float(persona.get("status_weight") or 0.0),
        }
        openings.append(row)
        observed.append((vector, float(persona.get("status_weight") or 0.0)))

    vectors = [row["vector"] for row in openings]
    first = openings[0]
    max_status = max(float(seated[s].get("status_weight") or 0.0) for s in order)
    transcript_body = {
        "mode": mode,
        "seed": int(seed),
        "spec_id": spec.get("id"),
        "speak_order": order,
        "labels": labels,
        "verdict": _verdict(vectors, labels),
        "openings": [
            {
                "seat_id": row["seat_id"],
                "published_name": row["published_name"],
                "text": row["text"],
                "vector": row["vector"],
            }
            for row in openings
        ],
    }
    out = {
        "mode": mode,
        "seed": int(seed),
        "spec_id": spec.get("id"),
        "hash": _canonical_hash(transcript_body),
        "verdict": transcript_body["verdict"],
        "openings": openings,
        "openings_by_speak_order": openings,
        "first_speaker_id": first["seat_id"],
        "first_speaker_high_status": abs(first["status_weight"] - max_status) < 1e-12,
        "blind_first_pass": blind_first_pass,
        "identity_published": identity_published,
        "labels": labels,
        "speak_order": order,
    }
    return out


def run_many(
    spec: Mapping[str, Any],
    personas: Sequence[Mapping[str, Any]],
    seeds: Iterable[int],
) -> list[dict[str, Any]]:
    return [run_council(spec, personas, int(seed)) for seed in seeds]
