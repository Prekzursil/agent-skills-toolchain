"""Seeded stratified confirmation sampler for CNF-0003.

Census every P0 and P1 claim. Draw P2 and P3 with a recorded seed so a
reviewer re-draws the identical id list. Detection n answers: what
per-stratum sample size detects a 10 percent class error rate at 90
percent confidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_REGISTRY = "command-center/CLAIM-REGISTRY.json"
FREEZE_REL = "command-center/p2-wave/probes/CNF-0003/fixtures/claim-population.json"
CNF0011_REL = "command-center/confirmation/CNF-0011-scheduler-report.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PHASE_GRAPH_REL = "command-center/PHASE-GRAPH.json"

UNIT_ID = "CNF-0003"
SEED = 20260824
P_CLASS_ERROR = 0.10
CONFIDENCE = 0.90
CENSUS_SEVERITIES = ("P0", "P1")
SAMPLE_SEVERITIES = ("P2", "P3")
ALL_SEVERITIES = CENSUS_SEVERITIES + SAMPLE_SEVERITIES

PLANTED_COUNTS = {"P0": 5, "P1": 8, "P2": 40, "P3": 40}
SUBSYSTEMS = ("confirmation", "catalog", "harness", "scheduler", "schema")
VENDORS = ("anthropic", "openai", "xai")
CLAIM_TYPES = ("invariant", "coverage", "policy", "measurement")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def canonical_id_list(ids: list[str]) -> str:
    return json.dumps(ids, ensure_ascii=True, separators=(",", ":"))


def infinite_population_n(p: float = P_CLASS_ERROR, confidence: float = CONFIDENCE) -> int:
    """Smallest n with P(at least one error | true rate p) >= confidence.

    1 - (1-p)^n >= confidence  =>  n >= ln(1-confidence)/ln(1-p)
    """
    if not (0.0 < p < 1.0) or not (0.0 < confidence < 1.0):
        raise ValueError("p and confidence must be in (0, 1)")
    ratio = math.log(1.0 - confidence) / math.log(1.0 - p)
    return int(math.ceil(ratio - 1e-12))


def detection_probability(n: int, p: float = P_CLASS_ERROR) -> float:
    return 1.0 - (1.0 - p) ** n


def hypergeometric_p0(n_pop: int, n_defective: int, n_draw: int) -> float:
    """P(X=0) drawing n_draw from n_pop with n_defective defectives."""
    if n_draw <= 0:
        return 1.0
    if n_draw > n_pop - n_defective:
        return 0.0
    p0 = 1.0
    for i in range(n_draw):
        p0 *= (n_pop - n_defective - i) / (n_pop - i)
    return p0


def finite_population_n(
    n_pop: int, p: float = P_CLASS_ERROR, confidence: float = CONFIDENCE
) -> int:
    """Smallest n such that P(at least one defective) >= confidence when
    K = ceil(p * N) defectives exist in the stratum.
    """
    if n_pop <= 0:
        return 0
    n_defective = max(1, int(math.ceil(p * n_pop - 1e-12)))
    n_defective = min(n_defective, n_pop)
    for n_draw in range(0, n_pop + 1):
        detected = 1.0 - hypergeometric_p0(n_pop, n_defective, n_draw)
        if detected >= confidence - 1e-15:
            return n_draw
    return n_pop


def sample_size_record() -> dict[str, Any]:
    n_inf = infinite_population_n()
    ln_conf = math.log(1.0 - CONFIDENCE)
    ln_p = math.log(1.0 - P_CLASS_ERROR)
    ratio = ln_conf / ln_p
    p21 = detection_probability(21)
    p22 = detection_probability(22)
    return {
        "p_class_error": P_CLASS_ERROR,
        "confidence": CONFIDENCE,
        "formula": "n = ceil(ln(1-confidence)/ln(1-p)); finite n from hypergeometric P(X>=1)>=confidence with K=ceil(p N)",
        "infinite_population_n": n_inf,
        "log_derivation": {
            "ln_one_minus_confidence": ln_conf,
            "ln_one_minus_p": ln_p,
            "ratio": ratio,
            "ceil": n_inf,
        },
        "n21_detection_probability": p21,
        "n22_detection_probability": p22,
        "n21_meets_confidence": p21 >= CONFIDENCE,
        "n22_meets_confidence": p22 >= CONFIDENCE,
        "function": "command-center/p2-wave/probes/CNF-0003/sampler.py:infinite_population_n",
        "finite_function": "command-center/p2-wave/probes/CNF-0003/sampler.py:finite_population_n",
    }


def stratum_rng(seed: int, stratum_id: str) -> random.Random:
    material = f"{int(seed)}|{stratum_id}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return random.Random(int(digest[:16], 16))


def draw_ids(population_ids: list[str], n_draw: int, seed: int, stratum_id: str) -> list[str]:
    ordered = sorted(population_ids)
    if n_draw <= 0:
        return []
    if n_draw >= len(ordered):
        return list(ordered)
    rng = stratum_rng(seed, stratum_id)
    return rng.sample(ordered, n_draw)


def planted_claims() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for severity, count in PLANTED_COUNTS.items():
        for i in range(1, count + 1):
            rows.append(
                {
                    "id": f"CLAIM-{severity}-{i:04d}",
                    "severity": severity,
                    "subsystem": SUBSYSTEMS[(i - 1) % len(SUBSYSTEMS)],
                    "author_vendor": VENDORS[(i - 1) % len(VENDORS)],
                    "claim_type": CLAIM_TYPES[(i - 1) % len(CLAIM_TYPES)],
                    "planted": True,
                    "statement": (
                        f"Planted {severity} claim {i:04d} used as the CNF-0003 "
                        "sampling-frame freeze because live CLAIM-REGISTRY.json is absent."
                    ),
                }
            )
    return rows


def _rows_from_doc(doc: Any) -> list[Any]:
    if isinstance(doc, list):
        return doc
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "records", "items", "entries"):
        val = doc.get(key)
        if isinstance(val, list):
            return val
    rows: list[Any] = []
    skip = {
        "schema_version",
        "meta",
        "provenance",
        "contract",
        "defaults",
        "work_units",
        "items",
    }
    for key, val in doc.items():
        if key in skip or str(key).startswith("_"):
            continue
        if isinstance(val, dict) and (
            val.get("id") or val.get("claim_id") or val.get("severity") or val.get("priority")
        ):
            row = dict(val)
            row.setdefault("id", key)
            rows.append(row)
    return rows


def normalize_claim(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"claim is not an object: {type(raw).__name__}")
    cid = str(raw.get("id") or raw.get("claim_id") or "").strip()
    if not cid:
        raise ValueError("claim missing id")
    sev = str(raw.get("severity") or raw.get("priority") or raw.get("grade") or "").strip().upper()
    if sev not in ALL_SEVERITIES:
        raise ValueError(
            f"claim {cid} missing or invalid severity {sev!r}; "
            "null/unknown severity must fail the frame build, not default to low"
        )
    return {
        "id": cid,
        "severity": sev,
        "subsystem": str(raw.get("subsystem") or raw.get("component") or "unspecified"),
        "author_vendor": str(raw.get("author_vendor") or raw.get("vendor") or "unspecified"),
        "claim_type": str(raw.get("claim_type") or raw.get("type") or "unspecified"),
        "planted": bool(raw.get("planted", False)),
        "statement": str(raw.get("statement") or raw.get("claim") or raw.get("text") or ""),
    }


def inspect_live_registry() -> dict[str, Any]:
    """Load the named registry without inventing P0-P3 grades.

    Missing severity is recorded, never defaulted to low. A mix of graded
    and ungraded rows is a hard failure: dropping the ungraded rows would
    silently shrink the denominator.
    """
    path = REPO / LIVE_REGISTRY
    meta: dict[str, Any] = {
        "path": LIVE_REGISTRY,
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "raw_count": 0,
        "graded": [],
        "ungraded_ids": [],
        "invalid": [],
    }
    if not path.is_file():
        return meta
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"live CLAIM-REGISTRY.json unparseable: {type(exc).__name__}: {exc}") from exc
    rows = _rows_from_doc(doc)
    meta["raw_count"] = len(rows)
    for row in rows:
        if not isinstance(row, dict):
            meta["invalid"].append({"id": None, "error": f"row is {type(row).__name__}"})
            continue
        cid = str(row.get("id") or row.get("claim_id") or "").strip()
        sev = str(row.get("severity") or row.get("priority") or row.get("grade") or "").strip().upper()
        if sev in ALL_SEVERITIES:
            meta["graded"].append(normalize_claim(row))
            continue
        meta["ungraded_ids"].append(cid or "<missing-id>")
    return meta


def load_live_claims() -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    """Backward-compatible wrapper: graded live claims or None if unusable."""
    meta = inspect_live_registry()
    if not meta["present"]:
        return None, meta
    if meta["graded"] and not meta["ungraded_ids"] and not meta["invalid"]:
        meta["count"] = len(meta["graded"])
        return list(meta["graded"]), meta
    if meta["graded"] and (meta["ungraded_ids"] or meta["invalid"]):
        raise ValueError(
            "live CLAIM-REGISTRY.json mixes graded and ungraded claims; "
            "refusing to drop ungraded rows or default them to low: "
            f"graded={len(meta['graded'])} ungraded={meta['ungraded_ids'][:12]}"
        )
    return None, meta


def resolve_population() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    live, live_meta = load_live_claims()
    if live is not None:
        source = {
            "kind": "live-claim-registry",
            "live_registry_path": LIVE_REGISTRY,
            "live_registry_present": True,
            "live_registry_bytes": live_meta.get("bytes"),
            "live_raw_count": live_meta.get("raw_count"),
            "live_ungraded_ids": [],
            "freeze_path": FREEZE_REL,
            "count": len(live),
        }
        return live, source
    planted = planted_claims()
    present = bool(live_meta.get("present"))
    ungraded = list(live_meta.get("ungraded_ids") or [])
    if present:
        kind = "unit-fixture-because-live-registry-has-no-severity"
        note = (
            "command-center/CLAIM-REGISTRY.json is present but none of its "
            f"{live_meta.get('raw_count', 0)} claims carry a P0-P3 severity "
            f"(ids={ungraded}). Severity was not invented from verdict/band. "
            "The sampling frame is frozen on the unit fixture population so "
            "P0/P1 census and the seed+1 control are executable and non-vacuous. "
            "Planted CLAIM-P*-NNNN ids are not the CC-* program claims."
        )
    else:
        kind = "unit-fixture-because-live-registry-absent"
        note = (
            "command-center/CLAIM-REGISTRY.json is absent on this tree. "
            "The sampling frame is frozen on the unit fixture population so the "
            "seeded sampler and the required seed controls are executable. "
            "These ids are planted CLAIM-P*-NNNN records, not program claims."
        )
    source = {
        "kind": kind,
        "live_registry_path": LIVE_REGISTRY,
        "live_registry_present": present,
        "live_registry_bytes": int(live_meta.get("bytes") or 0),
        "live_raw_count": int(live_meta.get("raw_count") or 0),
        "live_ungraded_ids": ungraded,
        "freeze_path": FREEZE_REL,
        "count": len(planted),
        "note": note,
    }
    return planted, source


def missing_severity_control() -> dict[str, Any]:
    """Both-states: a claim with no severity must fail loud, not become P3."""
    try:
        normalize_claim({"id": "CLAIM-NULL-SEV", "statement": "severity omitted on purpose"})
    except ValueError as exc:
        return {"raised": True, "error": str(exc)}
    return {"raised": False, "error": ""}


def sampling_view(art: dict[str, Any]) -> dict[str, Any]:
    """Read sampling fields from report payload or a legacy top-level frame."""
    if not isinstance(art, dict):
        raise ValueError("artifact is not an object")
    rpt = art.get("report") if isinstance(art.get("report"), dict) else {}
    view = dict(rpt)
    for key in (
        "seed",
        "drawn_ids",
        "strata",
        "drawn_ids_canonical_json",
        "same_seed_reproduction",
        "different_seed_control",
        "p0_p1_set_difference",
        "sample_size",
        "population_source",
        "required_confirmers",
        "cnf_0011_arrival_rate_cap",
        "partition_proof",
        "allocation_buckets",
    ):
        if key in art:
            view[key] = art[key]
    return view


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def write_freeze(claims: list[dict[str, Any]]) -> dict[str, Any]:
    path = REPO / FREEZE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "unit_id": UNIT_ID,
        "role": "sampling-frame-population-freeze",
        "claims": claims,
    }
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(path)
    return {"path": FREEZE_REL, "sha256": digest, "bytes": size, "count": len(claims)}


def claims_by_severity(claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets = {sev: [] for sev in ALL_SEVERITIES}
    seen: set[str] = set()
    for claim in claims:
        cid = claim["id"]
        if cid in seen:
            raise ValueError(f"duplicate claim id {cid}")
        seen.add(cid)
        buckets[claim["severity"]].append(cid)
    for sev in ALL_SEVERITIES:
        buckets[sev] = sorted(buckets[sev])
    return buckets


def partition_proof(claims: list[dict[str, Any]], buckets: dict[str, list[str]]) -> dict[str, Any]:
    total = len(claims)
    summed = sum(len(v) for v in buckets.values())
    intersections = []
    keys = list(ALL_SEVERITIES)
    for i, a in enumerate(keys):
        sa = set(buckets[a])
        for b in keys[i + 1 :]:
            both = sorted(sa & set(buckets[b]))
            if both:
                intersections.append({"a": a, "b": b, "ids": both})
    return {
        "claim_count": total,
        "stratum_count_sum": summed,
        "sum_equals_total": summed == total,
        "pairwise_intersections_empty": not intersections,
        "intersections": intersections,
    }


def build_strata(claims: list[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    buckets = claims_by_severity(claims)
    n_inf = infinite_population_n()
    strata: list[dict[str, Any]] = []
    for severity in ALL_SEVERITIES:
        pop_ids = buckets[severity]
        n_pop = len(pop_ids)
        n_finite = finite_population_n(n_pop)
        census = severity in CENSUS_SEVERITIES
        if census:
            mode = "census"
            n_draw = n_pop
        else:
            n_draw = min(n_pop, n_finite)
            mode = "census" if n_draw >= n_pop else "sample"
        stratum_id = f"severity:{severity}"
        drawn = draw_ids(pop_ids, n_draw, seed, stratum_id)
        strata.append(
            {
                "id": stratum_id,
                "severity": severity,
                "mode": mode,
                "population": n_pop,
                "draw": n_draw,
                "n_detect_infinite": n_inf,
                "n_detect_finite": n_finite,
                "k_assumed_defectives": (
                    0
                    if n_pop <= 0
                    else min(n_pop, max(1, int(math.ceil(P_CLASS_ERROR * n_pop - 1e-12))))
                ),
                "population_ids": pop_ids,
                "drawn_ids": drawn,
            }
        )
    return strata


def concat_drawn(strata: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in strata:
        out.extend(row["drawn_ids"])
    return out


def redraw_from_strata(strata: list[dict[str, Any]], seed: int) -> list[str]:
    """Re-draw using recorded per-stratum population_ids and the given seed."""
    out: list[str] = []
    for row in strata:
        pop = list(row.get("population_ids") or [])
        n_draw = int(row.get("draw") or 0)
        sid = str(row.get("id") or "")
        out.extend(draw_ids(pop, n_draw, seed, sid))
    return out


def p0_p1_set_difference(claims: list[dict[str, Any]], drawn_ids: list[str]) -> dict[str, Any]:
    registry = {c["id"] for c in claims if c["severity"] in CENSUS_SEVERITIES}
    frame_p0p1 = {
        cid
        for cid in drawn_ids
        if any(c["id"] == cid and c["severity"] in CENSUS_SEVERITIES for c in claims)
    }
    missing = sorted(registry - frame_p0p1)
    extra = sorted(frame_p0p1 - registry)
    return {
        "registry_p0p1_count": len(registry),
        "frame_p0p1_count": len(frame_p0p1),
        "registry_minus_frame": missing,
        "frame_p0p1_minus_registry": extra,
        "registry_minus_frame_empty": not missing,
        "frame_p0p1_minus_registry_empty": not extra,
    }


def allocation_buckets() -> dict[str, Any]:
    phase_path = REPO / PHASE_GRAPH_REL
    catalog_path = REPO / CATALOG_REL
    counts: dict[str, int] = {}
    missing = 0
    n_units = 0
    meta_target = None
    phase_buckets: list[dict[str, Any]] = []
    spec_floor = None
    measured_sum = None
    sum_matches_floor = None
    if phase_path.is_file():
        phase = json.loads(phase_path.read_text(encoding="utf-8"))
        ab = phase.get("allocation_buckets") if isinstance(phase, dict) else None
        if isinstance(ab, dict):
            spec_floor = ab.get("spec_floor_units")
            measured_sum = ab.get("measured_sum")
            sum_matches_floor = ab.get("sum_matches_floor")
            raw = ab.get("buckets") or []
            if isinstance(raw, list):
                for row in raw:
                    if not isinstance(row, dict) or not row.get("id"):
                        continue
                    phase_buckets.append(
                        {
                            "id": str(row["id"]),
                            "units": row.get("units"),
                            "name": row.get("name"),
                            "spec_line": row.get("spec_line"),
                        }
                    )
    if catalog_path.is_file():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        units = catalog.get("work_units") or []
        n_units = len(units) if isinstance(units, list) else 0
        if isinstance(units, list):
            for unit in units:
                if not isinstance(unit, dict):
                    continue
                bucket = unit.get("bucket")
                if bucket:
                    key = str(bucket)
                    counts[key] = counts.get(key, 0) + 1
                else:
                    missing += 1
        meta = catalog.get("work_units_meta") if isinstance(catalog, dict) else {}
        if isinstance(meta, dict):
            meta_target = meta.get("target")
    phase_present = phase_path.is_file()
    if phase_buckets:
        source = "command-center/PHASE-GRAPH.json#allocation_buckets"
        buckets = phase_buckets
    else:
        source = (
            "command-center/WORK-UNIT-CATALOG.json work_units[].bucket "
            "(PHASE-GRAPH.json#allocation_buckets absent or empty on this tree)"
        )
        buckets = [{"id": key, "count": counts[key]} for key in sorted(counts)]
    return {
        "phase_graph_path": PHASE_GRAPH_REL,
        "phase_graph_present": phase_present,
        "source": source,
        "spec_floor_units": spec_floor,
        "measured_sum": measured_sum,
        "sum_matches_floor": sum_matches_floor,
        "buckets": buckets,
        "catalog_bucket_counts": [{"id": key, "count": counts[key]} for key in sorted(counts)],
        "bucketed_unit_count": sum(counts.values()),
        "units_missing_bucket": missing,
        "work_unit_count": n_units,
        "catalog_target": meta_target,
    }


def cnf_0011_cap(required_confirmers: int) -> dict[str, Any]:
    path = REPO / CNF0011_REL
    rec: dict[str, Any] = {
        "published": False,
        "path": CNF0011_REL,
        "required_confirmers": required_confirmers,
        "fits_under_cap": None,
        "verdict": "NOT-CHECKED",
        "cap_value": None,
        "cap_unit": None,
        "reason": (
            "CNF-0011-scheduler-report.json is absent on this tree, so no "
            "arrival-rate cap has been published. Required confirmer count is "
            "recorded; fit vs that cap is NOT-CHECKED, not assumed true."
        ),
    }
    if not path.is_file():
        return rec
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        rec["reason"] = f"CNF-0011 report unparseable: {type(exc).__name__}: {exc}"
        return rec
    rec["published"] = True
    cap = None
    if isinstance(doc, dict):
        for key in (
            "arrival_rate_cap",
            "per_vendor_rate_cap",
            "rate_cap",
            "configured_rate",
            "concurrency",
        ):
            val = doc.get(key)
            if isinstance(val, (int, float)):
                cap = float(val)
                rec["cap_key"] = key
                break
            if isinstance(val, dict):
                for inner in ("cap", "limit", "max", "value"):
                    if isinstance(val.get(inner), (int, float)):
                        cap = float(val[inner])
                        rec["cap_key"] = f"{key}.{inner}"
                        break
            if cap is not None:
                break
    rec["cap_value"] = cap
    if cap is None:
        rec["verdict"] = "NOT-CHECKED"
        rec["reason"] = "CNF-0011 report present but no numeric arrival-rate cap field found"
        return rec
    rec["fits_under_cap"] = required_confirmers <= cap
    rec["verdict"] = "YES" if rec["fits_under_cap"] else "NO"
    rec["reason"] = (
        f"required_confirmers={required_confirmers} compared to published cap={cap}"
    )
    return rec


def catalog_unit() -> dict[str, Any]:
    catalog = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise KeyError("CNF-0003 missing from WORK-UNIT-CATALOG.json")


def build_frame(seed: int = SEED) -> dict[str, Any]:
    claims, source = resolve_population()
    if not claims:
        raise ValueError("sampling population is empty")
    freeze = write_freeze(claims)
    source = dict(source)
    source["freeze_sha256"] = freeze["sha256"]
    source["freeze_bytes"] = freeze["bytes"]
    strata = build_strata(claims, seed=seed)
    drawn = concat_drawn(strata)
    alt_strata = build_strata(claims, seed=seed + 1)
    alt_drawn = concat_drawn(alt_strata)
    same_json = canonical_id_list(drawn)
    alt_json = canonical_id_list(alt_drawn)
    sampled = [row for row in strata if row["mode"] == "sample"]
    if not sampled:
        raise ValueError(
            "every stratum was a census so seed+1 cannot differ; "
            "need at least one P2/P3 stratum with n < N"
        )
    if same_json == alt_json:
        raise ValueError("seed+1 produced an identical id list; seed is not consumed")
    diff = p0_p1_set_difference(claims, drawn)
    if not diff["registry_minus_frame_empty"] or not diff["frame_p0p1_minus_registry_empty"]:
        raise ValueError(f"P0/P1 census set-difference failed: {diff}")
    proof = partition_proof(claims, claims_by_severity(claims))
    if not proof["sum_equals_total"] or not proof["pairwise_intersections_empty"]:
        raise ValueError(f"severity strata do not partition: {proof}")
    required = sum(row["draw"] for row in strata)
    return {
        "claims": claims,
        "source": source,
        "freeze": freeze,
        "strata": strata,
        "drawn_ids": drawn,
        "same_seed_json": same_json,
        "alt_seed": seed + 1,
        "alt_drawn_ids": alt_drawn,
        "alt_seed_json": alt_json,
        "p0_p1_set_difference": diff,
        "partition_proof": proof,
        "required_confirmers": required,
        "cnf_0011": cnf_0011_cap(required),
        "allocation_buckets": allocation_buckets(),
        "sample_size": sample_size_record(),
        "seed": seed,
    }
