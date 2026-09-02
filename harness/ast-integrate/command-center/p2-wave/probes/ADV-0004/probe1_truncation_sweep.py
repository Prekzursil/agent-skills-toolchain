#!/usr/bin/env python3
"""Probe 1: truncation sweep of each schema reference artifact.

Byte-prefix at 5% increments and JSON structural-token offsets, plus
closed-prefix (re-closed object after the first N keys). Records the
schema-reader, G-1-like, and sentinel-substring verdicts per offset.
Also re-judges the shared IMP-0416 reducer against a truncated copy of
its positive-control artifact.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from common import (  # noqa: E402
    PERCENT_STEPS,
    PLANTED_SENTINEL,
    POSITIVE_WS_REL,
    REPO,
    UNIT,
    schema_paths,
)
from predicate import (  # noqa: E402
    g1_like_accepts,
    reducer_accepts,
    schema_accepts,
    sentinel_substring_accepts,
)
from synth import encode_sentinel_first, synthesize_schema, validate_instance  # noqa: E402

LOOSE_SCHEMA = _HERE / "fixtures" / "loose.schema.json"


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0004-probe1 {msg}")
    return 1


def structural_offsets(raw: bytes) -> list[int]:
    out = {0, len(raw)}
    in_str = False
    esc = False
    for i, b in enumerate(raw):
        if in_str:
            if esc:
                esc = False
                continue
            if b == 0x5C:  # backslash
                esc = True
                continue
            if b == 0x22:  # quote
                in_str = False
                out.add(i + 1)
            continue
        if b == 0x22:
            in_str = True
            continue
        if b in b"{}[],:":
            out.add(i + 1)
    return sorted(o for o in out if 0 <= o <= len(raw))


def percent_offsets(raw: bytes) -> list[tuple[str, int]]:
    n = len(raw)
    rows = []
    for pct in PERCENT_STEPS:
        off = 0 if n == 0 else min(n, int(round(n * pct / 100.0)))
        rows.append((f"pct-{pct}", off))
    return rows


def closed_prefixes(raw: bytes) -> list[tuple[str, bytes, int]]:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict) or not doc:
        return []
    keys = list(doc.keys())
    rows = []
    for i in range(1, len(keys) + 1):
        sub = {k: doc[k] for k in keys[:i]}
        blob = json.dumps(sub, indent=2, ensure_ascii=True).encode("utf-8")
        rows.append((f"closed-keys-{i}/{len(keys)}", blob, i))
    return rows


def _sentinel_token(inst: Any) -> str:
    if isinstance(inst, dict) and isinstance(inst.get("sentinel"), str):
        return inst["sentinel"]
    return "SUCCESS:ADV-0004-REF"


def sweep_bytes(raw: bytes, schema: dict, sentinel: str) -> dict[str, Any]:
    n = len(raw)
    points = []
    seen_off = set()
    for label, off in percent_offsets(raw):
        seen_off.add(off)
        prefix = raw[:off]
        points.append(
            {
                "kind": "percent",
                "label": label,
                "offset": off,
                "frac": (off / n) if n else 0.0,
                "schema": schema_accepts(prefix, schema),
                "g1": g1_like_accepts(prefix, sentinel),
                "sentinel_sub": sentinel_substring_accepts(prefix, sentinel),
            }
        )
    struct_pts = []
    for off in structural_offsets(raw):
        if off in seen_off:
            continue
        prefix = raw[:off]
        struct_pts.append(
            {
                "kind": "structural",
                "label": f"struct-{off}",
                "offset": off,
                "frac": (off / n) if n else 0.0,
                "schema": schema_accepts(prefix, schema),
                "g1": g1_like_accepts(prefix, sentinel),
                "sentinel_sub": sentinel_substring_accepts(prefix, sentinel),
            }
        )
    closed = []
    for label, blob, k in closed_prefixes(raw):
        closed.append(
            {
                "kind": "closed-prefix",
                "label": label,
                "keys_kept": k,
                "bytes": len(blob),
                "schema": schema_accepts(blob, schema),
                "g1": g1_like_accepts(blob, sentinel),
                "sentinel_sub": sentinel_substring_accepts(blob, sentinel),
            }
        )
    return {
        "bytes": n,
        "percent": points,
        "structural_count": len(struct_pts) + len(seen_off),
        "structural_accept_schema": sum(
            1 for p in struct_pts if p["schema"]["accept"]
        ),
        "structural_sample": struct_pts[:8] + struct_pts[-4:],
        "closed_prefix": closed,
    }


def curve_summary(percent_points: list[dict[str, Any]], reader: str) -> dict[str, Any]:
    accepts = [p[reader]["accept"] for p in percent_points]
    empty = percent_points[0][reader]["accept"] if percent_points else None
    full = percent_points[-1][reader]["accept"] if percent_points else None
    first_accept = next((p["frac"] for p in percent_points if p[reader]["accept"]), None)
    last_reject = None
    for p in percent_points:
        if not p[reader]["accept"]:
            last_reject = p["frac"]
    # Monotone: once True, later points stay True.
    saw_accept = False
    monotone = True
    for a in accepts:
        if a:
            saw_accept = True
        elif saw_accept:
            monotone = False
            break
    truncated_accepts = [
        p["frac"] for p in percent_points if p["frac"] < 1.0 and p[reader]["accept"]
    ]
    return {
        "empty_accept": empty,
        "full_accept": full,
        "first_accept_frac": first_accept,
        "last_reject_frac": last_reject,
        "has_transition": bool(empty is False and full is True),
        "monotone": monotone,
        "truncated_accept_fracs": truncated_accepts,
    }


def sweep_schema(path: Path) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    inst = synthesize_schema(schema)
    errs = validate_instance(schema, inst)
    raw = encode_sentinel_first(inst)
    sentinel = _sentinel_token(inst)
    if errs:
        return {
            "schema": path.name,
            "rel": path.relative_to(REPO).as_posix(),
            "ok": False,
            "synth_errors": errs[:5],
        }
    swept = sweep_bytes(raw, schema, sentinel)
    return {
        "schema": path.name,
        "rel": path.relative_to(REPO).as_posix(),
        "ok": True,
        "bytes": swept["bytes"],
        "sentinel_in_instance": isinstance(inst, dict) and "sentinel" in inst,
        "has_padding": isinstance(inst, dict)
        and "_adv0004_payload_tail" in inst,
        "percent_schema": curve_summary(swept["percent"], "schema"),
        "percent_g1": curve_summary(swept["percent"], "g1"),
        "percent_sentinel_sub": curve_summary(swept["percent"], "sentinel_sub"),
        "closed_prefix_schema_accepts": [
            c["label"] for c in swept["closed_prefix"] if c["schema"]["accept"]
        ],
        "closed_prefix_schema_rejects": [
            c["label"] for c in swept["closed_prefix"] if not c["schema"]["accept"]
        ],
        "closed_prefix_g1_accepts": [
            c["label"] for c in swept["closed_prefix"] if c["g1"]["accept"]
        ],
        "structural_count": swept["structural_count"],
        "structural_schema_accepts_excluding_full": swept["structural_accept_schema"],
        "percent_points": [
            {
                "label": p["label"],
                "offset": p["offset"],
                "frac": p["frac"],
                "schema": p["schema"]["accept"],
                "g1": p["g1"]["accept"],
                "sentinel_sub": p["sentinel_sub"]["accept"],
                "schema_reason": p["schema"]["reason"],
            }
            for p in swept["percent"]
        ],
        "closed_prefix": [
            {
                "label": c["label"],
                "keys_kept": c["keys_kept"],
                "schema": c["schema"]["accept"],
                "g1": c["g1"]["accept"],
                "sentinel_sub": c["sentinel_sub"]["accept"],
            }
            for c in swept["closed_prefix"]
        ],
    }


def planted_loose() -> dict[str, Any]:
    schema = json.loads(LOOSE_SCHEMA.read_text(encoding="utf-8"))
    inst = {
        "sentinel": PLANTED_SENTINEL,
        "payload": "P" * 3000,
    }
    raw = encode_sentinel_first(inst)
    swept = sweep_bytes(raw, schema, PLANTED_SENTINEL)
    return {
        "schema": "loose.schema.json",
        "bytes": len(raw),
        "percent_schema": curve_summary(swept["percent"], "schema"),
        "percent_g1": curve_summary(swept["percent"], "g1"),
        "percent_sentinel_sub": curve_summary(swept["percent"], "sentinel_sub"),
        "closed_prefix": [
            {
                "label": c["label"],
                "keys_kept": c["keys_kept"],
                "schema": c["schema"]["accept"],
                "g1": c["g1"]["accept"],
                "sentinel_sub": c["sentinel_sub"]["accept"],
            }
            for c in swept["closed_prefix"]
        ],
        "percent_points": [
            {
                "label": p["label"],
                "frac": p["frac"],
                "schema": p["schema"]["accept"],
                "g1": p["g1"]["accept"],
                "sentinel_sub": p["sentinel_sub"]["accept"],
            }
            for p in swept["percent"]
        ],
    }


def reducer_truncation() -> dict[str, Any]:
    src = REPO / POSITIVE_WS_REL
    if not src.is_dir():
        return {"ok": False, "reason": "positive-workspace-missing"}
    work = _HERE / "runtime" / "reducer-trunc"
    if work.exists():
        shutil.rmtree(work)
    rows = []
    art_src = src / "artifact.json"
    raw = art_src.read_bytes()
    n = len(raw)
    for pct in PERCENT_STEPS:
        dest = work / f"p{pct:03d}"
        shutil.copytree(src, dest)
        off = 0 if n == 0 else min(n, int(round(n * pct / 100.0)))
        (dest / "artifact.json").write_bytes(raw[:off])
        judged = reducer_accepts(dest)
        rows.append(
            {
                "pct": pct,
                "offset": off,
                "accept": judged["accept"],
                "verdict": judged.get("verdict"),
                "failing": judged.get("failing"),
                "exit_consulted": judged.get("exit_code_consulted_for_complete"),
            }
        )
    full = next(r for r in rows if r["pct"] == 100)
    empty = next(r for r in rows if r["pct"] == 0)
    return {
        "ok": True,
        "artifact_bytes": n,
        "empty_accept": empty["accept"],
        "full_accept": full["accept"],
        "truncated_accepts": [r["pct"] for r in rows if r["pct"] < 100 and r["accept"]],
        "rows": rows,
    }


def main() -> int:
    planted = planted_loose()
    live = []
    failed_synth = []
    for path in schema_paths():
        row = sweep_schema(path)
        if not row.get("ok"):
            failed_synth.append(row)
        live.append(row)

    reducer = reducer_truncation()

    # Controls
    empty_ok = planted["percent_schema"]["empty_accept"] is False
    full_ok = planted["percent_schema"]["full_accept"] is True
    trans_ok = planted["percent_schema"]["has_transition"] is True
    live_ok = [r for r in live if r.get("ok")]
    if not live_ok:
        return _fail("no schema produced a valid reference artifact")
    live_empty = all(r["percent_schema"]["empty_accept"] is False for r in live_ok)
    live_full = all(r["percent_schema"]["full_accept"] is True for r in live_ok)
    live_trans = all(r["percent_schema"]["has_transition"] for r in live_ok)
    live_mono = all(r["percent_schema"]["monotone"] for r in live_ok)

    # Sentinel-substring must accept some truncated prefix of the planted
    # sentinel-first artifact (otherwise we are not measuring that reader).
    planted_sub = planted["percent_sentinel_sub"]
    sub_hits_truncated = bool(planted_sub["truncated_accept_fracs"])
    schema_rejects_those = planted["percent_schema"]["truncated_accept_fracs"] == []

    # Closed prefix keeping only sentinel (1/2 keys) must schema-accept on loose.
    loose_closed_one = next(
        (c for c in planted["closed_prefix"] if c["keys_kept"] == 1),
        None,
    )
    closed_sentinel_only = bool(loose_closed_one and loose_closed_one["schema"])

    reducer_ok = (
        reducer.get("ok")
        and reducer.get("empty_accept") is False
        and reducer.get("full_accept") is True
        and reducer.get("truncated_accepts") == []
    )

    controls = {
        "planted_empty_rejects": empty_ok,
        "planted_full_accepts": full_ok,
        "planted_has_transition": trans_ok,
        "live_empty_rejects": live_empty,
        "live_full_accepts": live_full,
        "live_has_transition": live_trans,
        "live_monotone": live_mono,
        "sentinel_sub_accepts_truncated_planted": sub_hits_truncated,
        "schema_rejects_byte_truncated_planted": schema_rejects_those,
        "loose_closed_prefix_sentinel_only_schema_accepts": closed_sentinel_only,
        "reducer_empty_rejects": reducer.get("empty_accept") is False,
        "reducer_full_accepts": reducer.get("full_accept") is True,
        "reducer_rejects_all_byte_truncations": reducer.get("truncated_accepts")
        == [],
        "synth_failed": len(failed_synth),
        "synth_ok": len(live_ok),
        "synth_total": len(live),
    }
    missing = [k for k, v in controls.items() if k.startswith("synth_")]
    required = [
        "planted_empty_rejects",
        "planted_full_accepts",
        "planted_has_transition",
        "live_empty_rejects",
        "live_full_accepts",
        "live_has_transition",
        "live_monotone",
        "sentinel_sub_accepts_truncated_planted",
        "schema_rejects_byte_truncated_planted",
        "loose_closed_prefix_sentinel_only_schema_accepts",
        "reducer_empty_rejects",
        "reducer_full_accepts",
        "reducer_rejects_all_byte_truncations",
    ]
    failed_controls = [k for k in required if not controls.get(k)]
    if failed_synth:
        return _fail(
            "synth failed for "
            + ",".join(r["schema"] for r in failed_synth[:8])
            + f" (+{max(0, len(failed_synth)-8)})"
        )
    if failed_controls:
        print(json.dumps({"controls": controls, "reducer": reducer}, indent=2, sort_keys=True)[:4000])
        return _fail("controls-failed:" + ",".join(failed_controls))

    schemas_byte_trunc_schema_accept = [
        r["schema"]
        for r in live_ok
        if r["percent_schema"]["truncated_accept_fracs"]
    ]
    schemas_closed_before_last = [
        r["schema"]
        for r in live_ok
        if any(
            c["schema"] and not c["label"].endswith(f"/{c['keys_kept']}")
            for c in r.get("closed_prefix") or []
        )
    ]
    # closed prefix that is not the full key set:
    schemas_closed_partial_ok = []
    for r in live_ok:
        cps = r.get("closed_prefix") or []
        if not cps:
            continue
        last_k = cps[-1]["keys_kept"]
        if any(c["schema"] and c["keys_kept"] < last_k for c in cps):
            schemas_closed_partial_ok.append(r["schema"])
    schemas_sentinel_sub_trunc = [
        r["schema"]
        for r in live_ok
        if r["percent_sentinel_sub"]["truncated_accept_fracs"]
    ]
    schemas_g1_trunc = [
        r["schema"]
        for r in live_ok
        if r["percent_g1"]["truncated_accept_fracs"]
    ]

    out = {
        "ok": True,
        "probe": "probe1-truncation-sweep",
        "unit_id": UNIT,
        "controls": controls,
        "planted_loose": planted,
        "reducer": reducer,
        "schema_count": len(live),
        "schemas_byte_truncation_schema_accepts": schemas_byte_trunc_schema_accept,
        "schemas_closed_prefix_partial_schema_accepts": schemas_closed_partial_ok,
        "schemas_sentinel_substring_accepts_truncation": schemas_sentinel_sub_trunc,
        "schemas_g1_accepts_truncation": schemas_g1_trunc,
        "first_accept_frac_by_schema": {
            r["schema"]: r["percent_schema"]["first_accept_frac"] for r in live_ok
        },
        "results": live,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:ADV-0004-probe1 "
        f"schemas={len(live_ok)} "
        f"byte_trunc_schema_accept={len(schemas_byte_trunc_schema_accept)} "
        f"closed_partial={len(schemas_closed_partial_ok)} "
        f"sentinel_sub_trunc={len(schemas_sentinel_sub_trunc)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
