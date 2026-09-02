"""Content-addressed two-wave tracker and per-class half-life MLE.

Half-life is measured from snapshot hash churn. A reputation table is not
consulted. Censored classes (zero observed changes) report a lower bound,
not an invented number.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Callable

from catalog import (
    ARCHIVED_TAG_ID,
    CLASSES,
    MIN_INTERVAL_HOURS,
    WAVE1_TS,
    WAVE2_TS,
    sources,
    wave1_body,
    wave2_body,
)

LN2 = math.log(2.0)
POLICY_FLOOR_HOURS = 168.0  # 7d — labeled policy, not a measured half-life


def sha256_text(text: str) -> str:
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def hours_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 3600.0


def snapshot_record(src: dict, wave: int, body: str, fetched_at: datetime) -> dict:
    digest = sha256_text(body)
    raw = body.encode("utf-8").replace(b"\r\n", b"\n")
    return {
        "wave": wave,
        "uri": f"{src['uri']}@wave{wave}",
        "fetched_at": fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": 200,
        "bytes": len(raw),
        "sha256": digest,
        "pin": {
            "kind": "content-addressed-sha256",
            "sha256": digest,
            "fixture_rev": f"wave{wave}",
        },
        "owner_gated": bool(src.get("owner_gated")),
        "stand_in": bool(src.get("stand_in")),
    }


def class_half_life(n: int, changed: int, dt_hours: float) -> dict:
    """Exponential MLE: λ = k / (n Δt), T½ = ln(2)/λ.

    k=0 is right-censored: T½ is a lower bound (> Δt), not a point estimate
    and not a reputation default.
    """
    if n < 1 or changed < 0 or changed > n:
        raise ValueError(f"bad n={n} changed={changed}")
    if dt_hours < MIN_INTERVAL_HOURS:
        raise ValueError(f"observation window {dt_hours}h < {MIN_INTERVAL_HOURS}h")
    exposure = n * dt_hours
    if changed == 0:
        trigger = max(2.0 * dt_hours, POLICY_FLOOR_HOURS)
        return {
            "n_sources": n,
            "n_changed": 0,
            "n_unchanged": n,
            "observation_hours": dt_hours,
            "exposure_source_hours": exposure,
            "lambda_per_hour": 0.0,
            "half_life_hours": None,
            "half_life_days": None,
            "bound": "lower",
            "lower_bound_hours": dt_hours,
            "revalidation_trigger_hours": trigger,
            "revalidation_trigger_source": "policy-floor-unobserved-change-not-reputation",
            "method": "exponential-mle-from-snapshot-churn",
        }
    lam = changed / exposure
    hl = LN2 / lam
    return {
        "n_sources": n,
        "n_changed": changed,
        "n_unchanged": n - changed,
        "observation_hours": dt_hours,
        "exposure_source_hours": exposure,
        "lambda_per_hour": lam,
        "half_life_hours": hl,
        "half_life_days": hl / 24.0,
        "bound": "point-mle",
        "lower_bound_hours": None,
        "revalidation_trigger_hours": hl,
        "revalidation_trigger_source": "measured-half-life",
        "method": "exponential-mle-from-snapshot-churn",
    }


def measure(
    *,
    mutate_source_id: str | None = None,
    mutate_fn: Callable[[str], str] | None = None,
) -> dict:
    dt = hours_between(WAVE1_TS, WAVE2_TS)
    rows: list[dict] = []
    for src in sources():
        b1 = wave1_body(src)
        b2 = wave2_body(src)
        if mutate_source_id == src["id"] and mutate_fn is not None:
            b2 = mutate_fn(b2)
        s1 = snapshot_record(src, 1, b1, WAVE1_TS)
        s2 = snapshot_record(src, 2, b2, WAVE2_TS)
        changed = s1["sha256"] != s2["sha256"]
        rows.append(
            {
                "id": src["id"],
                "source_class": src["source_class"],
                "uri": src["uri"],
                "static_control": src["static_control"],
                "decay_on_write": src["decay_on_write"],
                "owner_gated": src["owner_gated"],
                "changed": changed,
                "interval_hours": dt,
                "snapshots": [s1, s2],
            }
        )

    by_class: dict[str, dict] = {}
    for cls in CLASSES:
        members = [r for r in rows if r["source_class"] == cls]
        k = sum(1 for r in members if r["changed"])
        stats = class_half_life(len(members), k, dt)
        stats["source_class"] = cls
        stats["source_ids"] = [r["id"] for r in members]
        by_class[cls] = stats

    table = [by_class[c] for c in CLASSES]
    archived = next(r for r in rows if r["id"] == ARCHIVED_TAG_ID)
    return {
        "n_sources": len(rows),
        "n_classes": len(CLASSES),
        "n_changed": sum(1 for r in rows if r["changed"]),
        "n_unchanged": sum(1 for r in rows if not r["changed"]),
        "observation_hours": dt,
        "interval_ok": dt >= MIN_INTERVAL_HOURS,
        "min_snapshots": 2,
        "archived_tag": {
            "id": ARCHIVED_TAG_ID,
            "changed": archived["changed"],
            "churn": 1 if archived["changed"] else 0,
            "wave1_sha256": archived["snapshots"][0]["sha256"],
            "wave2_sha256": archived["snapshots"][1]["sha256"],
        },
        "sources": rows,
        "half_life_table": table,
        "by_id": {r["id"]: r for r in rows},
        "by_class": by_class,
        "formula": "lambda=k/(n*dt_hours); half_life_hours=ln(2)/lambda if k>0 else censored-lower-bound",
    }


def reputation_mutant_table(dt_hours: float) -> list[dict]:
    """Known-broken: assign half-life from class reputation, ignore snapshots."""
    assumed_days = {
        "official-docs": 30.0,
        "source-code": 14.0,
        "issue-tracker": 3.0,
        "papers": 365.0,
        "blog-post": 14.0,
        "forums": 7.0,
        "practitioner-report": 21.0,
        "video-talk": 90.0,
        "archival": 3650.0,
        "multilingual": 60.0,
        "niche-forum": 14.0,
        "prior-art-patent": 365.0,
        "standards-regulatory": 180.0,
        "marketplace": 7.0,
        "release-changelog": 2.0,
        "public-tor": 7.0,
    }
    out = []
    for cls in CLASSES:
        hl = assumed_days[cls] * 24.0
        out.append(
            {
                "source_class": cls,
                "half_life_hours": hl,
                "method": "reputation-prior",
                "observation_hours": dt_hours,
                "ignored_snapshots": True,
            }
        )
    return out
