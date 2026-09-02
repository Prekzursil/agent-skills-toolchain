#!/usr/bin/env python3
"""Mechanical tests for RES-0070: field necessity + uncacheable control."""
from __future__ import annotations

from typing import Any

from spec import (
    CACHE_KEY_FIELDS,
    FIELD_IDS,
    UNCACHEABLE_LIVE_WEB,
    UNCACHEABLE_SAMPLER,
    UncacheableStep,
    base_step,
    classify,
    compute_key,
    url_only_mutant_key,
)


def _vary(field_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    a = base_step()
    b = base_step()
    if field_id == "step_mnemonic":
        b["step_mnemonic"] = "retrieve"
    elif field_id == "model_identity":
        b["model_revision"] = "2025-01-01"
    elif field_id == "sampling_parameters":
        b["temperature"] = 1
    elif field_id == "prompt_bytes_sha256":
        b["prompt_bytes_sha256"] = "e" * 64
    elif field_id == "tool_policy_sha256":
        b["tool_policy_sha256"] = "f" * 64
    elif field_id == "declared_input_artifact_sha256s":
        b["declared_input_artifact_sha256s"] = ["g" * 64]
    elif field_id == "live_source_snapshot_sha256":
        b["live_source_snapshot_sha256"] = "h" * 64
    elif field_id == "declared_env":
        b["declared_env"] = {"REGION": "eu"}
    else:
        raise KeyError(field_id)
    return a, b


def field_necessity() -> dict[str, Any]:
    rows = []
    all_ok = True
    for field in CACHE_KEY_FIELDS:
        fid = field["id"]
        a, b = _vary(fid)
        ka = compute_key(a)
        kb = compute_key(b)
        differ = ka != kb
        collide_when_omitted = compute_key(a, omit=fid) == compute_key(b, omit=fid)
        ok = bool(differ and collide_when_omitted)
        all_ok = all_ok and ok
        rows.append(
            {
                "id": fid,
                "justification": field["justification"],
                "keys_differ_when_field_present": differ,
                "keys_collide_when_field_omitted": collide_when_omitted,
                "ok": ok,
            }
        )
    k1 = compute_key(base_step())
    k2 = compute_key(base_step())
    stable = k1 == k2
    return {
        "pass": bool(all_ok and stable and len(rows) == len(FIELD_IDS) and len(rows) >= 8),
        "field_count": len(rows),
        "stable_across_calls": stable,
        "fields": rows,
    }


def uncacheable_control() -> dict[str, Any]:
    live = base_step(live_source_snapshot_sha256=None)
    live_cls = classify(live)
    raised = None
    try:
        compute_key(live)
    except UncacheableStep as exc:
        raised = exc.class_id

    sampler = base_step(
        temperature=0.7,
        seed=None,
        deterministic_decoding=False,
        live_web_url=None,
        live_source_snapshot_sha256=None,
    )
    samp_cls = classify(sampler)
    samp_raised = None
    try:
        compute_key(sampler)
    except UncacheableStep as exc:
        samp_raised = exc.class_id

    body_a = base_step(live_source_snapshot_sha256="1" * 64)
    body_b = base_step(live_source_snapshot_sha256="2" * 64)
    honest_differ = compute_key(body_a) != compute_key(body_b)
    mutant_collide = url_only_mutant_key(body_a) == url_only_mutant_key(body_b)
    same_url = body_a["live_web_url"] == body_b["live_web_url"]

    ok = (
        live_cls == UNCACHEABLE_LIVE_WEB
        and raised == UNCACHEABLE_LIVE_WEB
        and samp_cls == UNCACHEABLE_SAMPLER
        and samp_raised == UNCACHEABLE_SAMPLER
        and honest_differ
        and mutant_collide
        and same_url
    )
    return {
        "pass": bool(ok),
        "live_web_class": live_cls,
        "live_web_raised": raised,
        "sampler_class": samp_cls,
        "sampler_raised": samp_raised,
        "honest_body_keys_differ": honest_differ,
        "url_only_mutant_collides": mutant_collide,
        "same_url": same_url,
        "named_uncacheable_class": UNCACHEABLE_LIVE_WEB,
        "named_uncacheable_class_sampler": UNCACHEABLE_SAMPLER,
    }
