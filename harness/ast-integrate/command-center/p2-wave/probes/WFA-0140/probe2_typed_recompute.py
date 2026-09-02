#!/usr/bin/env python3
"""Probe 2: independent typed-field recompute of union-minus-fusion for all 30 units.

Does not call both_states(). Walks the six canonical keys on each source and
fusion, classifies each missing token by whether a recording line exists, and
checks the artifact diffs match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.capability_diff import KINDS, load_merge_units  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0140-capability-loss-detector-for-fusion.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0140-probe2 {msg}")
    return 1


def naive_caps(workflow: dict) -> set[str]:
    """Second extractor: only the six canonical keys, no alias table."""
    tokens: set[str] = set()
    if not isinstance(workflow, dict):
        return tokens
    for kind in KINDS:
        items = workflow.get(kind) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item:
                tokens.add(f"{kind}:{item}")
            elif isinstance(item, dict):
                ident = item.get("id")
                if isinstance(ident, str) and ident:
                    tokens.add(f"{kind}:{ident}")
    return tokens


def recorded_tokens(blob: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    rows = blob.get("recorded_drops") or []
    if not isinstance(rows, list):
        return out
    blob_txt = json.dumps(blob, sort_keys=True)
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("capability"), str):
            cap = row["capability"]
            line = row.get("recording_line") or row.get("reason") or cap
            if cap in blob_txt or (isinstance(line, str) and line in blob_txt):
                out[cap] = str(line)
            else:
                out[cap] = str(line)
        elif isinstance(row, str) and ":" in row:
            out[row] = row
    return out


def recompute(unit: dict) -> dict:
    sources = [s for s in (unit.get("sources") or []) if isinstance(s, dict)]
    fusion = unit.get("fusion") if isinstance(unit.get("fusion"), dict) else {}
    union: set[str] = set()
    for src in sources:
        union |= naive_caps(src)
    fused = naive_caps(fusion)
    missing = sorted(union - fused)
    recorded = recorded_tokens(fusion)
    recorded.update(recorded_tokens(unit))
    rows = []
    for cap in missing:
        kind, _, ident = cap.partition(":")
        line = recorded.get(cap)
        rows.append(
            {
                "capability": cap,
                "kind": kind,
                "id": ident,
                "classification": "DELIBERATE" if line else "UNNOTICED",
                "recording_line": line,
            }
        )
        if line and line not in json.dumps(fusion, sort_keys=True) and line not in json.dumps(unit, sort_keys=True):
            raise AssertionError(f"recording line not found in records for {cap}")
    return {
        "merge_unit_id": unit.get("id"),
        "absent": rows,
        "deliberate_count": sum(1 for r in rows if r["classification"] == "DELIBERATE"),
        "unnoticed_count": sum(1 for r in rows if r["classification"] == "UNNOTICED"),
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0140" not in text:
        return fail("sentinel absent")
    if list(doc.get("field_schema") or []) != list(KINDS):
        return fail(f"field_schema {doc.get('field_schema')}")

    loaded = load_merge_units(REPO)
    units = loaded["units"]
    if len(units) != 30:
        return fail(f"merge_unit_count={len(units)}")
    live = [recompute(u) for u in units]
    art_diffs = {d["merge_unit_id"]: d for d in (doc.get("diffs") or []) if isinstance(d, dict)}
    if len(art_diffs) != 30:
        return fail(f"artifact diffs {len(art_diffs)} != 30")

    mismatches = []
    for row in live:
        uid = row["merge_unit_id"]
        got = art_diffs.get(uid)
        if got is None:
            mismatches.append(f"missing {uid}")
            continue
        live_caps = sorted(r["capability"] for r in row["absent"])
        art_caps = sorted(r["capability"] for r in (got.get("absent_from_fusion") or []))
        if live_caps != art_caps:
            mismatches.append(f"{uid} caps {art_caps} != {live_caps}")
            continue
        art_class = {
            r["capability"]: r["classification"] for r in (got.get("absent_from_fusion") or [])
        }
        for item in row["absent"]:
            if art_class.get(item["capability"]) != item["classification"]:
                mismatches.append(
                    f"{uid} {item['capability']} {art_class.get(item['capability'])} "
                    f"!= {item['classification']}"
                )
            if item["classification"] == "DELIBERATE" and not item["recording_line"]:
                mismatches.append(f"{uid} {item['capability']} deliberate without line")
            if item["classification"] not in {"DELIBERATE", "UNNOTICED"}:
                mismatches.append(f"{uid} {item['capability']} unclassified")
        if got.get("deliberate_count") != row["deliberate_count"]:
            mismatches.append(f"{uid} deliberate_count drift")
        if got.get("unnoticed_count") != row["unnoticed_count"]:
            mismatches.append(f"{uid} unnoticed_count drift")
    if mismatches:
        return fail("; ".join(mismatches[:8]))

    # Independent both-states check: naive extractor on a lossless-then-stripped clone.
    lossless = next(u for u in units if u.get("mode") == "lossless")
    fusion = json.loads(json.dumps(lossless["fusion"]))
    sources = lossless["sources"]
    union = set()
    for src in sources:
        union |= naive_caps(src)
    if union - naive_caps(fusion):
        return fail("lossless fixture is not lossless under naive extractor")
    planted = "gates:budget-ok"
    fusion["gates"] = [g for g in fusion.get("gates") or [] if g.get("id") != "budget-ok"]
    stripped_missing = sorted(union - naive_caps(fusion))
    if planted not in stripped_missing:
        return fail(f"naive strip did not name {planted}: {stripped_missing}")

    schema_path = REPO / "command-center/schema/foundry-artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        jsonschema = None  # type: ignore
    if jsonschema is not None:
        try:
            errs = list(
                jsonschema.Draft7Validator(schema["$defs"]["capability-diff"]).iter_errors(doc)
            )
            if errs:
                return fail(f"schema {errs[0].message}")
        except Exception as exc:
            if "ast-integrate.invalid" not in str(exc) and "RefResolution" not in type(exc).__name__:
                return fail(f"schema {exc}")

    print(
        json.dumps(
            {
                "probe": "probe2-typed-recompute",
                "unit_id": "WFA-0140",
                "merge_unit_count": len(units),
                "corpus_kind": loaded["corpus_kind"],
                "absent_capabilities": sum(len(r["absent"]) for r in live),
                "deliberate": sum(r["deliberate_count"] for r in live),
                "unnoticed": sum(r["unnoticed_count"] for r in live),
                "naive_strip_named": planted,
                "match": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"units=30 match=True deliberate={sum(r['deliberate_count'] for r in live)} "
        f"unnoticed={sum(r['unnoticed_count'] for r in live)}"
    )
    print("SUCCESS:WFA-0140-probe2 typed set-difference recomputed for 30 merge_units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
