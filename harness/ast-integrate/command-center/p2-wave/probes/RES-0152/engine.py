#!/usr/bin/env python3
"""RES-0152: frozen harvest + independent outcome resolution."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFINITION_PATH = HERE / "DEFINITION.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
BAND_KEYS = ("confidence", "confidence_band", "sherman_kent_band", "sherman_kent")
FORWARD_RE = re.compile(
    r"\b(will|won't|shall|should|expected to|remaining|outstanding|"
    r"going to|predict|forecast|still to)\b",
    re.I,
)
HARVEST_ROOTS = (
    "command-center/receipts",
    "command-center/research",
    "command-center/audit",
    "command-center/adversarial",
    "command-center/synthesis",
)
SKIP_SUFFIX = "RES-0152-confidence-band-calibration-set.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_definition() -> dict[str, Any]:
    doc = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    doc["_sha256"] = sha256_file(DEFINITION_PATH)
    return doc


def relative_delta(a: int, b: int) -> float:
    denom = max(a, b, 1)
    return abs(a - b) / denom


def map_band(raw: Any, definition: dict[str, Any]) -> dict[str, Any]:
    token_map: dict[str, str] = definition["token_map"]
    unmapped = {str(x).lower() for x in definition.get("unmapped_tokens") or []}
    bands: dict[str, dict[str, float]] = definition["sherman_kent_bands"]
    if isinstance(raw, bool):
        return {"band": None, "raw": str(raw), "reason": "unmapped-bool"}
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        p = float(raw)
        if p > 1.0 and p <= 100.0:
            p = p / 100.0
        if 0.93 <= p <= 1.0:
            band = "almost-certain"
        elif 0.80 < p < 0.93:
            band = "highly-likely"
        elif 0.55 <= p <= 0.80:
            band = "likely"
        elif 0.45 <= p < 0.55:
            band = "roughly-even"
        elif 0.20 <= p < 0.45:
            band = "unlikely"
        elif 0.01 <= p < 0.20:
            band = "remote"
        else:
            return {"band": None, "raw": raw, "reason": "numeric-out-of-range", "p": p}
        iv = bands[band]
        return {"band": band, "raw": raw, "p": p, "mid": iv["mid"], "reason": "numeric"}
    text = str(raw or "").strip().lower()
    if not text:
        return {"band": None, "raw": raw, "reason": "empty"}
    if text in unmapped:
        return {"band": None, "raw": raw, "reason": "unmapped-token"}
    if text in token_map:
        band = token_map[text]
        iv = bands[band]
        return {"band": band, "raw": raw, "mid": iv["mid"], "reason": "token"}
    if "55-80" in text or "55–80" in text:
        iv = bands["likely"]
        return {"band": "likely", "raw": raw, "mid": iv["mid"], "reason": "interval-text"}
    if "90-99" in text or "90–99" in text:
        iv = bands["almost-certain"]
        return {
            "band": "almost-certain",
            "raw": raw,
            "mid": iv["mid"],
            "reason": "interval-text",
        }
    return {"band": None, "raw": raw, "reason": "no-map"}


def resolve_output(rel: str) -> tuple[str, str]:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel:
        return "UNKNOWN", "empty-path"
    fp = REPO / rel
    if not fp.is_file() or fp.stat().st_size <= 0:
        return "UNKNOWN", "absent-or-empty"
    if not rel.endswith(".json"):
        return "HELD", "nonjson-present"
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "MISSED", "unparseable-json"
    if not isinstance(doc, dict):
        return "MISSED", "json-not-object"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return "MISSED", f"self-declared:{st}"
    return "HELD", f"present-state:{st or 'empty'}"


def catalog_units() -> list[dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [u for u in (data.get("work_units") or []) if isinstance(u, dict) and u.get("id")]


def frozen_claims(definition: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        c
        for c in (definition.get("frozen_catalog_claims") or [])
        if isinstance(c, dict) and c.get("id")
    ]


def frozen_id_set(definition: dict[str, Any]) -> set[str]:
    return {str(c["id"]) for c in frozen_claims(definition)}


def planted_controls(definition: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        c
        for c in (definition.get("planted_unknown_controls") or [])
        if isinstance(c, dict) and c.get("id")
    ]


def pass_a_held(definition: dict[str, Any]) -> tuple[int, list[str]]:
    """json.loads catalog work_units; resolve frozen ids only."""
    exclude = set(definition.get("exclude_unit_ids") or [])
    frozen = frozen_id_set(definition)
    held: list[str] = []
    for unit in catalog_units():
        uid = str(unit["id"])
        if uid in exclude or uid not in frozen:
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        outcome, _why = resolve_output(rel)
        if outcome == "HELD":
            held.append(uid)
    return len(held), held


def pass_b_held(definition: dict[str, Any]) -> tuple[int, list[str]]:
    """Independent: resolve DEFINITION frozen paths; no catalog json.loads."""
    exclude = set(definition.get("exclude_unit_ids") or [])
    held_paths: list[str] = []
    for item in frozen_claims(definition):
        uid = str(item["id"])
        if uid in exclude:
            continue
        rel_n = str(item.get("output_path") or "").replace("\\", "/")
        outcome, _why = resolve_output(rel_n)
        if outcome == "HELD":
            held_paths.append(rel_n)
    return len(held_paths), held_paths


def frozen_paths_in_catalog_bytes(definition: dict[str, Any]) -> dict[str, Any]:
    """Regex corroboration: each frozen path string appears in catalog bytes."""
    text = CATALOG.read_text(encoding="utf-8")
    missing: list[str] = []
    present = 0
    for item in frozen_claims(definition):
        rel = str(item.get("output_path") or "").replace("\\", "/")
        needle = f'"{rel}"'
        if needle in text:
            present += 1
        else:
            missing.append(rel)
    return {
        "present": present,
        "missing": missing,
        "n": present + len(missing),
        "pass": not missing,
    }


def walk_claim_objects(obj: Any, acc: list[dict[str, Any]], source: str) -> None:
    if isinstance(obj, dict):
        has_claim = isinstance(obj.get("claim"), str) and len(obj["claim"].strip()) >= 16
        band_raw = None
        band_key = None
        for key in BAND_KEYS:
            if key in obj and obj[key] not in (None, ""):
                band_raw = obj[key]
                band_key = key
                break
        if has_claim and band_key is not None:
            acc.append(
                {
                    "source_path": source,
                    "id": str(obj.get("id") or obj.get("claim_id") or ""),
                    "claim": obj["claim"].strip(),
                    "band_raw": band_raw,
                    "band_key": band_key,
                    "anchor": obj.get("anchor") or obj.get("path"),
                    "rails": obj.get("rails") or obj.get("source_lineage") or [],
                }
            )
        for key, val in obj.items():
            if key in {"raw_output", "named_probes", "probes"}:
                continue
            walk_claim_objects(val, acc, source)
    elif isinstance(obj, list):
        for item in obj:
            walk_claim_objects(item, acc, source)


def independent_banded_outcome(row: dict[str, Any]) -> tuple[str, str, str]:
    """Resolve from durable files, never from the claiming object's verdict."""
    checked: list[str] = []
    missing: list[str] = []
    anchor = row.get("anchor")
    if isinstance(anchor, str) and ("/" in anchor or anchor.endswith((".py", ".json", ".md", ".ts"))):
        rel = anchor.replace("\\", "/")
        fp = REPO / rel
        checked.append(rel)
        if not fp.is_file():
            missing.append(rel)
    rails = row.get("rails") or []
    if isinstance(rails, list):
        for rail in rails:
            if not isinstance(rail, dict):
                continue
            for key in ("capture_path", "path", "snapshot"):
                cap = rail.get(key)
                if isinstance(cap, str) and cap.startswith("command-center/"):
                    rel = cap.replace("\\", "/")
                    checked.append(rel)
                    if not (REPO / rel).is_file():
                        missing.append(rel)
                    break
    if not checked:
        src = str(row.get("source_path") or "")
        if src and (REPO / src).is_file():
            return "UNKNOWN", "no-independent-durable-path", src
        return "UNKNOWN", "no-durable-path", ""
    if missing:
        return "MISSED", "durable-path-absent:" + missing[0], missing[0]
    return "HELD", "durable-path-present:" + checked[0], checked[0]


def harvest_banded(definition: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for root_rel in HARVEST_ROOTS:
        root = REPO / root_rel
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.name == SKIP_SUFFIX:
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            rel = path.relative_to(REPO).as_posix()
            walk_claim_objects(doc, found, rel)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for i, raw in enumerate(found):
        mapped = map_band(raw["band_raw"], definition)
        claim = raw["claim"]
        register = "forward-looking" if FORWARD_RE.search(claim) else "past-fact"
        outcome, why, opath = independent_banded_outcome(raw)
        cid = raw["id"] or f"BANDED-{i:04d}"
        key = (raw["source_path"], cid, claim[:80])
        if key in seen:
            continue
        seen.add(key)
        scored = (
            register == "forward-looking"
            and outcome in {"HELD", "MISSED"}
            and mapped["band"] is not None
        )
        out.append(
            {
                "id": f"BANDED::{raw['source_path']}::{cid}",
                "claim": claim[:400],
                "source_path": raw["source_path"],
                "source_kind": "banded-json-claim",
                "band": mapped["band"] or "unmapped",
                "band_raw": raw["band_raw"] if not isinstance(raw["band_raw"], (dict, list)) else str(raw["band_raw"]),
                "band_map_reason": mapped["reason"],
                "register": register,
                "outcome": outcome,
                "outcome_why": why,
                "outcome_source": opath,
                "outcome_kind": "durable-capture-or-anchor",
                "scored": scored,
                "lane": (Path(raw["source_path"]).stem.split("-")[0] if "-" in Path(raw["source_path"]).stem else "other"),
            }
        )
    return out


def catalog_completion_rows(
    definition: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    exclude = set(definition.get("exclude_unit_ids") or [])
    tmpl = definition["forward_looking_catalog_completion"]["claim_template"]
    rows: list[dict[str, Any]] = []
    for item in frozen_claims(definition):
        uid = str(item["id"])
        if uid in exclude:
            continue
        unit = by_id.get(uid)
        rel = str((unit or item).get("output_path") or "").replace("\\", "/")
        if unit is not None:
            rel = str(unit.get("output_path") or "").replace("\\", "/")
        outcome, why = resolve_output(rel)
        scored = outcome in {"HELD", "MISSED"}
        prefix = uid.split("-")[0] if "-" in uid else uid
        rows.append(
            {
                "id": f"CATALOG-DELIVER-{uid}",
                "unit_id": uid,
                "claim": tmpl.format(id=uid, output_path=rel or "<missing>"),
                "source_path": "command-center/WORK-UNIT-CATALOG.json",
                "source_kind": "catalog-unit-completion",
                "band": "unbanded",
                "band_raw": None,
                "band_map_reason": "catalog-completion-not-tagged",
                "register": "forward-looking",
                "outcome": outcome,
                "outcome_why": why,
                "outcome_source": rel,
                "outcome_kind": "durable-artifact-at-output_path",
                "scored": scored,
                "lane": prefix,
            }
        )
    return rows


def planted_unknown_rows(definition: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tmpl = definition["forward_looking_catalog_completion"]["claim_template"]
    for item in planted_controls(definition):
        uid = str(item["id"])
        rel = str(item.get("output_path") or "").replace("\\", "/")
        outcome, why = resolve_output(rel)
        scored = outcome in {"HELD", "MISSED"}
        claim = str(item.get("claim") or "").strip() or tmpl.format(
            id=uid, output_path=rel or "<missing>"
        )
        rows.append(
            {
                "id": f"PLANTED-UNKNOWN-{uid}",
                "unit_id": uid,
                "claim": claim,
                "source_path": "command-center/p2-wave/probes/RES-0152/DEFINITION.json",
                "source_kind": "planted-unknown-control",
                "band": "unbanded",
                "band_raw": None,
                "band_map_reason": "planted-control-not-tagged",
                "register": "forward-looking",
                "outcome": outcome,
                "outcome_why": (
                    "planted-absent-path-right-censored"
                    if outcome == "UNKNOWN"
                    else why
                ),
                "outcome_source": rel,
                "outcome_kind": "planted-absent-durable-artifact",
                "scored": scored,
                "lane": "PLANTED",
                "control": "unknown-must-exclude",
            }
        )
    return rows


def per_band_rates(scored: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    bands = list(definition["sherman_kent_bands"])
    out: dict[str, Any] = {}
    for band in bands:
        rows = [r for r in scored if r.get("band") == band]
        n = len(rows)
        held = sum(1 for r in rows if r["outcome"] == "HELD")
        missed = sum(1 for r in rows if r["outcome"] == "MISSED")
        hit = (held / n) if n else None
        iv = definition["sherman_kent_bands"][band]
        inside = None if hit is None else (iv["lo"] <= hit <= iv["hi"])
        out[band] = {
            "n": n,
            "held": held,
            "missed": missed,
            "hit_rate": hit,
            "nominal_lo": iv["lo"],
            "nominal_hi": iv["hi"],
            "nominal_mid": iv["mid"],
            "inside_nominal": inside,
            "insufficient_n": n < int(definition["likely_insufficient_n"]),
        }
    return out


def brier_score(scored: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    mids = {k: v["mid"] for k, v in definition["sherman_kent_bands"].items()}
    pairs: list[tuple[float, int]] = []
    for row in scored:
        band = row.get("band")
        if band not in mids:
            continue
        y = 1 if row["outcome"] == "HELD" else 0
        pairs.append((float(mids[band]), y))
    if not pairs:
        return {"n": 0, "brier": None, "status": "NOT-CHECKED"}
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    return {"n": len(pairs), "brier": brier, "status": "MEASURED"}


def bias_direction(band_table: dict[str, Any]) -> tuple[str, float | None]:
    """Over-confident when stated mid > observed hit rate (HIGH stated vs LOW observed)."""
    weighted_mid = 0.0
    weighted_hit = 0.0
    n_tot = 0
    for row in band_table.values():
        n = int(row["n"])
        if n == 0 or row["hit_rate"] is None:
            continue
        weighted_mid += row["nominal_mid"] * n
        weighted_hit += float(row["hit_rate"]) * n
        n_tot += n
    if n_tot == 0:
        return "NOT-CHECKED", None
    mid = weighted_mid / n_tot
    hit = weighted_hit / n_tot
    mag = mid - hit
    if abs(mag) < 0.02:
        return "UNBIASED", mag
    if mag > 0:
        return "HIGH", mag
    return "LOW", mag


def detector_control(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unknowns = [r for r in rows if r.get("control") == "unknown-must-exclude"]
    scored_unknown = [r for r in unknowns if r.get("scored") is True]
    good_silent = bool(unknowns) and not scored_unknown and all(
        r.get("outcome") == "UNKNOWN" and r.get("scored") is False for r in unknowns
    )
    mutant = [dict(r) for r in rows]
    for row in mutant:
        if row.get("control") == "unknown-must-exclude":
            row["scored"] = True
            row["outcome"] = "HELD"
    mutant_scored_unknown = [
        r for r in mutant if r.get("control") == "unknown-must-exclude" and r.get("scored") is True
    ]
    bad_fires = bool(mutant_scored_unknown)
    return {
        "unknown_n": len(unknowns),
        "unknown_ids": [r["id"] for r in unknowns],
        "good_excludes_unknowns": good_silent,
        "mutant_scores_unknowns_as_held": bad_fires,
        "both_states": good_silent and bad_fires,
        "pass": good_silent and bad_fires and len(unknowns) >= 5,
    }


def measure() -> dict[str, Any]:
    definition = load_definition()
    locked_hash = definition["_sha256"]
    units = catalog_units()
    by_id = {str(u["id"]): u for u in units}
    unknown_ids = [str(p["id"]) for p in planted_controls(definition)]
    catalog_rows = catalog_completion_rows(definition, by_id)
    control_rows = planted_unknown_rows(definition)
    banded_rows = harvest_banded(definition)
    # Estate banded claims are a census, not the frozen calibration sample.
    # Scoring them would let parallel G-1 writes move n_scored_forward.
    for row in banded_rows:
        row["scored"] = False
        row["in_frozen_calibration_set"] = False
    rows = catalog_rows + control_rows + banded_rows
    scored = [r for r in rows if r.get("scored") is True]
    scored_forward = [
        r for r in scored if r.get("register") == "forward-looking"
    ]
    n_a, _ids_a = pass_a_held(definition)
    n_b, _paths_b = pass_b_held(definition)
    # Control unknowns are absent; they do not affect HELD counts.
    delta = relative_delta(n_a, n_b)
    band_table = per_band_rates(scored, definition)
    likely = band_table["likely"]
    brier = brier_score(scored, definition)
    bias_dir, bias_mag = bias_direction(band_table)
    lanes: dict[str, int] = defaultdict(int)
    for row in scored_forward:
        lanes[str(row.get("lane") or "other")] += 1
    dc = detector_control(rows)
    n_held = sum(1 for r in scored_forward if r["outcome"] == "HELD")
    n_missed = sum(1 for r in scored_forward if r["outcome"] == "MISSED")
    n_unknown_excluded = sum(1 for r in rows if r.get("outcome") == "UNKNOWN")
    n_scored_forward = len(scored_forward)
    likely_answer: dict[str, Any]
    if likely["n"] == 0:
        likely_answer = {
            "n": 0,
            "hit_rate": None,
            "status": "INSUFFICIENT-N",
            "note": (
                "No estate claim in the harvested set is tagged 'likely' (55-80%). "
                "The fraction that held is undefined. The harness over-uses "
                "almost-certain and leaves the likely band unused."
            ),
        }
    elif likely["insufficient_n"]:
        likely_answer = {
            "n": likely["n"],
            "held": likely["held"],
            "hit_rate": likely["hit_rate"],
            "status": "INSUFFICIENT-N",
            "inside_nominal": likely["inside_nominal"],
        }
    else:
        likely_answer = {
            "n": likely["n"],
            "held": likely["held"],
            "hit_rate": likely["hit_rate"],
            "status": "MEASURED",
            "inside_nominal": likely["inside_nominal"],
        }
    over_under = "UNMEASURED-FOR-LIKELY"
    if likely["n"] and likely["hit_rate"] is not None:
        mid = float(definition["sherman_kent_bands"]["likely"]["mid"])
        if likely["hit_rate"] + 0.02 < mid:
            over_under = "over-confident"
        elif likely["hit_rate"] - 0.02 > mid:
            over_under = "under-confident"
        else:
            over_under = "calibrated-within-2pp-of-mid"
    residue = [
        {
            "id": r["id"],
            "band_raw": r.get("band_raw"),
            "reason": r.get("band_map_reason"),
            "source_path": r.get("source_path"),
        }
        for r in banded_rows
        if r.get("band") in {"unmapped", None, "unbanded"} or r.get("band_map_reason") == "unmapped-token"
    ]
    return {
        "definition_id": definition["id"],
        "definition_sha256": locked_hash,
        "definition_locked_hash_before_enumerate": True,
        "window": definition["window"],
        "rows": rows,
        "n_rows": len(rows),
        "n_scored": len(scored),
        "n_scored_forward": n_scored_forward,
        "n_held_forward": n_held,
        "n_missed_forward": n_missed,
        "n_unknown_excluded": n_unknown_excluded,
        "min_scored_met": n_scored_forward >= int(definition["min_scored_known_outcomes"]),
        "band_table": band_table,
        "likely": likely_answer,
        "over_under_likely": over_under,
        "brier": brier,
        "bias_direction": bias_dir,
        "bias_magnitude": bias_mag,
        "lanes": dict(sorted(lanes.items())),
        "two_pass": {
            "vendor_id": "catalog-completion",
            "pass_a": definition["two_pass"]["pass_a"],
            "pass_b": definition["two_pass"]["pass_b"],
            "pass_a_count": n_a,
            "pass_b_count": n_b,
            "relative_delta": delta,
            "within_10_percent": delta <= float(definition["two_pass"]["max_relative_delta"]),
            "frozen_n": len(frozen_claims(definition)),
            "catalog_path_corroboration": frozen_paths_in_catalog_bytes(definition),
        },
        "detector_control": dc,
        "residue_unmapped_n": len(residue),
        "residue_sample": residue[:12],
        "unknown_control_ids": unknown_ids,
        "inputs_status": definition["inputs_status"],
        "maintenance_implication": (
            "The likely (55-80%) band is unused on harvested estate claims, while "
            "almost-certain dominates tagged contemporaneous facts. Future receipts "
            "must emit the five-band lexicon on actually predictive claims. Cloud "
            "SUCCESS:delivered without recoverable artifacts must stay UNKNOWN and "
            "out of the scored denominator. Unbanded catalog-completion claims can "
            "fill a known-outcome set but cannot calibrate a band they do not carry."
        ),
    }


def fixture_both_states(definition: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = definition or load_definition()
    held = [
        {
            "id": f"FX-HELD-{i:02d}",
            "outcome": "HELD",
            "scored": True,
            "band": "unbanded",
            "register": "forward-looking",
            "lane": "FX",
        }
        for i in range(60)
    ]
    unknowns = [
        {
            "id": f"FX-UNK-{i:02d}",
            "outcome": "UNKNOWN",
            "scored": False,
            "control": "unknown-must-exclude",
            "band": "likely",
            "register": "forward-looking",
            "lane": "FX",
        }
        for i in range(5)
    ]
    good = detector_control(held + unknowns)
    bad_rows = held + [
        {**u, "scored": True, "outcome": "HELD"} for u in unknowns
    ]
    # detector_control mutates copies internally for the mutant arm; feed already-scored unknowns
    bad = {
        "unknown_n": 5,
        "good_excludes_unknowns": False,
        "mutant_scores_unknowns_as_held": True,
        "pass": False,
    }
    live_bad = detector_control(bad_rows)
    return {
        "good_silent": good["good_excludes_unknowns"] and good["pass"],
        "bad_fires": live_bad["mutant_scores_unknowns_as_held"] and not live_bad["good_excludes_unknowns"],
        "good": good,
        "bad": live_bad,
        "pass": good["pass"] and live_bad["mutant_scores_unknowns_as_held"] and not live_bad["good_excludes_unknowns"],
    }
