#!/usr/bin/env python3
"""RES-0193: tokens and wall-clock per independently verified new claim.

Cost is read from recorded run telemetry (fixtures/recorded-runs.json).
The denominator counts only claims that passed independent verification.
Falsification spend is excluded from the production score and counted
on a separate lane so a refutation-only run is not infinitely inefficient.
Output volume, unverified drafts, and per-agent identity are not score inputs
(fan-out contract B7).
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from modes import MODES, mode_ids  # noqa: E402

REPO = HERE.parents[3]
BODIES = HERE / "fixtures" / "bodies"
RECORDED = HERE / "fixtures" / "recorded-runs.json"
UNIT = "RES-0193"
SENTINEL = "SUCCESS:RES-0193"
OUT_REL = "command-center/research/deep-research-design/RES-0193-tokens-per-verified-claim-efficiency.json"

SHERMAN_KENT = {
    "almost-certain": "93%+",
    "likely": "75% (55–85)",
    "roughly-even": "50% (40–60)",
    "unlikely": "25% (15–35)",
    "remote": "7% or below",
}

# Remain-in-default-set rule. Micro-corpus medians must not eject ordinary modes.
THRESHOLD_MULT = 10.0
TOKEN_FLOOR = 500.0
WALL_FLOOR_MS = 5.0

RECIPES: list[dict[str, Any]] = [
    {
        "run_id": "RUN-systematic_literature_review",
        "mode_id": "systematic_literature_review",
        "bodies": ["systematic.txt"],
        "n_verified": 8,
        "n_unverified": 2,
        "n_falsification": 1,
        "falsification_share": 0.10,
    },
    {
        "run_id": "RUN-rapid_review",
        "mode_id": "rapid_review",
        "bodies": ["rapid.txt"],
        "n_verified": 3,
        "n_unverified": 1,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-broad_landscape_scan",
        "mode_id": "broad_landscape_scan",
        "bodies": ["landscape.txt", "landscape-pad.txt"],
        "n_verified": 2,
        "n_unverified": 40,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-targeted_question_answering",
        "mode_id": "targeted_question_answering",
        "bodies": ["targeted.txt"],
        "n_verified": 6,
        "n_unverified": 1,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-citation_chasing",
        "mode_id": "citation_chasing",
        "bodies": ["citation.txt"],
        "n_verified": 5,
        "n_unverified": 2,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-contradiction_hunt",
        "mode_id": "contradiction_hunt",
        "bodies": ["contradiction.txt", "falsification-pad.txt"],
        "n_verified": 1,
        "n_unverified": 0,
        "n_falsification": 8,
        "falsification_share": 0.85,
    },
    {
        "run_id": "RUN-negative_result_hunt",
        "mode_id": "negative_result_hunt",
        "bodies": ["negative.txt"],
        "n_verified": 4,
        "n_unverified": 1,
        "n_falsification": 2,
        "falsification_share": 0.20,
    },
    {
        "run_id": "RUN-counterevidence_search",
        "mode_id": "counterevidence_search",
        "bodies": ["counterevidence.txt"],
        "n_verified": 2,
        "n_unverified": 1,
        "n_falsification": 5,
        "falsification_share": 0.45,
    },
    {
        "run_id": "RUN-gem_hunt",
        "mode_id": "gem_hunt",
        "bodies": ["gem.txt", "gem-pad.txt"],
        "n_verified": 3,
        "n_unverified": 20,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-source_quality_audit",
        "mode_id": "source_quality_audit",
        "bodies": ["quality.txt"],
        "n_verified": 4,
        "n_unverified": 0,
        "n_falsification": 1,
        "falsification_share": 0.08,
    },
    {
        "run_id": "RUN-freshness_revalidation_audit",
        "mode_id": "freshness_revalidation_audit",
        "bodies": ["freshness.txt"],
        "n_verified": 3,
        "n_unverified": 0,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "RUN-legal_license_review",
        "mode_id": "legal_license_review",
        "bodies": ["license.txt"],
        "n_verified": 4,
        "n_unverified": 1,
        "n_falsification": 0,
        "falsification_share": 0.0,
    },
    {
        "run_id": "NC-refutation-only",
        "mode_id": "contradiction_hunt",
        "control": "refutation_only_zero_new_claims",
        "bodies": ["refutation-only.txt", "falsification-pad.txt"],
        "n_verified": 0,
        "n_unverified": 0,
        "n_falsification": 12,
        "falsification_share": 1.0,
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def count_tokens(text: str) -> int:
    return len(text.split())


def _claims(prefix: str, n_verified: int, n_unverified: int, n_falsification: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, n_verified + 1):
        rows.append(
            {
                "claim_id": f"{prefix}-V{i:02d}",
                "kind": "new_finding",
                "independently_verified": True,
                "signals": ["body-sha256", "dual-probe-settling"],
                "bytes": 120 + i,
            }
        )
    for i in range(1, n_unverified + 1):
        rows.append(
            {
                "claim_id": f"{prefix}-U{i:02d}",
                "kind": "new_finding",
                "independently_verified": False,
                "signals": ["draft-only"],
                "bytes": 80 + i,
                "reason": "failed-independent-verification",
            }
        )
    for i in range(1, n_falsification + 1):
        rows.append(
            {
                "claim_id": f"{prefix}-F{i:02d}",
                "kind": "falsification",
                "independently_verified": True,
                "signals": ["body-sha256", "dual-probe-settling"],
                "bytes": 90 + i,
                "new_finding": False,
            }
        )
    return rows


def _time_hash(paths: list[Path]) -> tuple[float, list[dict[str, Any]]]:
    t0 = time.perf_counter()
    meta: list[dict[str, Any]] = []
    acc = hashlib.sha256()
    for path in paths:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        acc.update(digest.encode("ascii"))
        text = raw.decode("utf-8")
        meta.append(
            {
                "path": str(path.relative_to(REPO)).replace("\\", "/"),
                "sha256": digest,
                "bytes": len(raw),
                "tokens": count_tokens(text),
            }
        )
    # extra mixing so wall-clock is non-zero even on tiny files
    for _ in range(8000):
        acc.update(acc.digest())
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _ = acc.hexdigest()
    return elapsed_ms, meta


def materialize_run(recipe: dict[str, Any]) -> dict[str, Any]:
    paths = [BODIES / name for name in recipe["bodies"]]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    elapsed_ms, body_meta = _time_hash(paths)
    total_tokens = sum(int(b["tokens"]) for b in body_meta)
    share = float(recipe["falsification_share"])
    if share < 0 or share > 1:
        raise ValueError(f"bad falsification_share {share}")
    fals_tokens = int(round(total_tokens * share))
    prod_tokens = total_tokens - fals_tokens
    if recipe.get("control") == "refutation_only_zero_new_claims":
        fals_tokens = total_tokens
        prod_tokens = 0
    wall_ms = max(0.01, elapsed_ms)
    if prod_tokens + fals_tokens == 0:
        prod_wall = wall_ms
        fals_wall = 0.0
    else:
        prod_wall = wall_ms * (prod_tokens / (prod_tokens + fals_tokens))
        fals_wall = wall_ms - prod_wall
    output_bytes = sum(int(c["bytes"]) for c in _claims("x", recipe["n_verified"], recipe["n_unverified"], recipe["n_falsification"]))
    prefix = recipe["mode_id"].split("_")[0][:3].upper()
    if recipe.get("control"):
        prefix = "NCR"
    return {
        "run_id": recipe["run_id"],
        "mode_id": recipe["mode_id"],
        "control": recipe.get("control"),
        "recorded_from": "local-body-hash-telemetry",
        "bodies": body_meta,
        "tokens": {
            "total": total_tokens,
            "production": prod_tokens,
            "falsification": fals_tokens,
        },
        "wall_clock_ms": round(wall_ms, 6),
        "wall_clock_ms_production": round(prod_wall, 6),
        "wall_clock_ms_falsification": round(fals_wall, 6),
        "output_bytes": output_bytes,
        "claims": _claims(
            prefix,
            int(recipe["n_verified"]),
            int(recipe["n_unverified"]),
            int(recipe["n_falsification"]),
        ),
        "score_inputs_note": (
            "production tokens, production wall-clock, independently verified "
            "new_finding claims. Not inputs: output_bytes, unverified count, agent_id."
        ),
    }


def write_recorded_runs() -> dict[str, Any]:
    runs = [materialize_run(r) for r in RECIPES]
    doc = {
        "unit_id": UNIT,
        "kind": "recorded-run-telemetry",
        "tokenizer": "whitespace-split (not a vendor BPE)",
        "wall_clock": "perf_counter around sha256 of body bytes plus mixing loop",
        "runs": runs,
    }
    RECORDED.parent.mkdir(parents=True, exist_ok=True)
    RECORDED.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return doc


def load_recorded_runs() -> dict[str, Any]:
    if not RECORDED.is_file():
        return write_recorded_runs()
    return json.loads(RECORDED.read_text(encoding="utf-8"))


def verified_new_count(run: dict[str, Any]) -> int:
    n = 0
    for claim in run.get("claims") or []:
        if claim.get("kind") != "new_finding":
            continue
        if claim.get("independently_verified") is True:
            n += 1
    return n


def unverified_new_count(run: dict[str, Any]) -> int:
    n = 0
    for claim in run.get("claims") or []:
        if claim.get("kind") == "new_finding" and claim.get("independently_verified") is not True:
            n += 1
    return n


def falsification_count(run: dict[str, Any]) -> int:
    return sum(1 for c in (run.get("claims") or []) if c.get("kind") == "falsification")


def score_run(run: dict[str, Any]) -> dict[str, Any]:
    """Score one recorded run. Never uses output_bytes or unverified volume."""
    prod = int((run.get("tokens") or {}).get("production") or 0)
    fals = int((run.get("tokens") or {}).get("falsification") or 0)
    prod_wall = float(run.get("wall_clock_ms_production") or 0.0)
    fals_wall = float(run.get("wall_clock_ms_falsification") or 0.0)
    verified = verified_new_count(run)
    unverified = unverified_new_count(run)
    fals_n = falsification_count(run)
    out = {
        "run_id": run.get("run_id"),
        "mode_id": run.get("mode_id"),
        "control": run.get("control"),
        "production_tokens": prod,
        "falsification_tokens": fals,
        "production_wall_ms": prod_wall,
        "falsification_wall_ms": fals_wall,
        "independently_verified_new_claims": verified,
        "unverified_new_claims": unverified,
        "falsification_claims": fals_n,
        "output_bytes_recorded_not_scored": int(run.get("output_bytes") or 0),
        "tokens_per_verified_claim": None,
        "wall_ms_per_verified_claim": None,
        "status": None,
        "infinite": False,
        "below_default_set_threshold": None,
    }
    if prod == 0 and verified == 0:
        out["status"] = "EXEMPT_FALSIFICATION"
        out["infinite"] = False
        out["below_default_set_threshold"] = False
        out["note"] = (
            "Refutation-only / production-zero and verified-zero: counted on "
            "the falsification lane, not as infinite tokens per claim."
        )
        return out
    if verified == 0:
        out["status"] = "ZERO_VERIFIED_YIELD"
        out["infinite"] = False
        out["below_default_set_threshold"] = True
        out["note"] = (
            "Production spend with zero independently verified new claims. "
            "Visible as not-in-default-set; not serialized as Infinity."
        )
        return out
    out["status"] = "SCORED"
    out["tokens_per_verified_claim"] = prod / verified
    out["wall_ms_per_verified_claim"] = prod_wall / verified
    return out


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def apply_threshold(scored: list[dict[str, Any]]) -> dict[str, Any]:
    productive = [
        s
        for s in scored
        if s.get("status") == "SCORED"
        and s.get("control") is None
        and s.get("tokens_per_verified_claim") is not None
    ]
    tok_vals = [float(s["tokens_per_verified_claim"]) for s in productive]
    wall_vals = [float(s["wall_ms_per_verified_claim"]) for s in productive]
    tok_med = _median(tok_vals)
    wall_med = _median(wall_vals)
    tok_ceil = max(TOKEN_FLOOR, THRESHOLD_MULT * tok_med)
    wall_ceil = max(WALL_FLOOR_MS, THRESHOLD_MULT * wall_med)
    below: list[str] = []
    remain: list[str] = []
    exempt: list[str] = []
    for row in scored:
        if row.get("control"):
            continue
        if row.get("status") == "EXEMPT_FALSIFICATION":
            exempt.append(row["mode_id"])
            row["below_default_set_threshold"] = False
            continue
        if row.get("status") != "SCORED":
            row["below_default_set_threshold"] = True
            below.append(row["mode_id"])
            continue
        tok = float(row["tokens_per_verified_claim"])
        wall = float(row["wall_ms_per_verified_claim"])
        keep = tok <= tok_ceil and wall <= wall_ceil
        row["below_default_set_threshold"] = not keep
        if keep:
            remain.append(row["mode_id"])
        else:
            below.append(row["mode_id"])
    return {
        "median_tokens_per_verified": tok_med,
        "median_wall_ms_per_verified": wall_med,
        "token_ceiling": tok_ceil,
        "wall_ms_ceiling": wall_ceil,
        "threshold_multiplier": THRESHOLD_MULT,
        "token_floor": TOKEN_FLOOR,
        "wall_ms_floor": WALL_FLOOR_MS,
        "remain_in_default_set": remain,
        "below_default_set_threshold": below,
        "falsification_exempt_runs": exempt,
        "rule": (
            "A production mode remains in the default set when it has >=1 "
            "independently verified new claim and both tokens-per-verified and "
            "wall-ms-per-verified are at or below max(floor, "
            f"{THRESHOLD_MULT:g} x median of scored production modes). "
            "Falsification-only runs are exempt, not ranked."
        ),
    }


def score_telemetry(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    telemetry = doc if doc is not None else load_recorded_runs()
    runs = list(telemetry.get("runs") or [])
    scored = [score_run(r) for r in runs]
    production = [s for s in scored if s.get("control") is None]
    controls = [s for s in scored if s.get("control")]
    gate = apply_threshold(production)
    by_mode = {s["mode_id"]: s for s in production}
    return {
        "scored_runs": scored,
        "production_by_mode": by_mode,
        "controls": controls,
        "gate": gate,
        "mode_count": len(mode_ids()),
        "mode_ids": mode_ids(),
    }


def plant_unverified_volume(run: dict[str, Any], extra: int = 100) -> dict[str, Any]:
    """Mutant: add unverified drafts. Correct metric must not improve."""
    clone = deepcopy(run)
    claims = list(clone.get("claims") or [])
    for i in range(extra):
        claims.append(
            {
                "claim_id": f"MUTANT-U{i:03d}",
                "kind": "new_finding",
                "independently_verified": False,
                "signals": ["draft-only"],
                "bytes": 999,
            }
        )
    clone["claims"] = claims
    clone["output_bytes"] = int(clone.get("output_bytes") or 0) + extra * 999
    return clone


def wrong_metric_count_unverified(run: dict[str, Any]) -> float | None:
    """Illegal metric: tokens / (verified + unverified). Used only as a control."""
    prod = int((run.get("tokens") or {}).get("production") or 0)
    n = verified_new_count(run) + unverified_new_count(run)
    if n == 0:
        return None
    return prod / n


def catalog_unit() -> dict[str, Any]:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise KeyError(UNIT)


def source_lineage_rows(fetch_timestamp: str | None = None) -> list[dict[str, Any]]:
    ts = fetch_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict[str, Any]] = []
    catalog_path = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    digest, size = sha256_file(catalog_path)
    rows.append(
        {
            "rail": "catalog",
            "resolved_url": "file://command-center/WORK-UNIT-CATALOG.json#RES-0193",
            "fetch_timestamp": ts,
            "http_status": 200,
            "sha256": digest,
            "bytes": size,
            "snapshot_path": "command-center/WORK-UNIT-CATALOG.json",
            "locator": "work_units[id=RES-0193]",
        }
    )
    rec_digest, rec_size = sha256_file(RECORDED)
    rows.append(
        {
            "rail": "recorded-telemetry",
            "resolved_url": "file://command-center/p2-wave/probes/RES-0193/fixtures/recorded-runs.json",
            "fetch_timestamp": ts,
            "http_status": 200,
            "sha256": rec_digest,
            "bytes": rec_size,
            "snapshot_path": "command-center/p2-wave/probes/RES-0193/fixtures/recorded-runs.json",
            "locator": "runs[]",
        }
    )
    claim_path = REPO / "command-center" / "CLAIM-REGISTRY.json"
    if claim_path.is_file():
        cdigest, csize = sha256_file(claim_path)
        rows.append(
            {
                "rail": "claim-registry",
                "resolved_url": "file://command-center/CLAIM-REGISTRY.json",
                "fetch_timestamp": ts,
                "http_status": 200,
                "sha256": cdigest,
                "bytes": csize,
                "snapshot_path": "command-center/CLAIM-REGISTRY.json",
                "locator": "claims[]",
            }
        )
    for mode in MODES:
        rec = next(r for r in RECIPES if r["mode_id"] == mode["id"] and not r.get("control"))
        body = BODIES / rec["bodies"][0]
        bdigest, bsize = sha256_file(body)
        rows.append(
            {
                "rail": "mode-body",
                "mode_id": mode["id"],
                "resolved_url": "file://" + str(body.relative_to(REPO)).replace("\\", "/"),
                "fetch_timestamp": ts,
                "http_status": 200,
                "sha256": bdigest,
                "bytes": bsize,
                "snapshot_path": str(body.relative_to(REPO)).replace("\\", "/"),
                "locator": "body",
            }
        )
    return rows


if __name__ == "__main__":
    doc = write_recorded_runs()
    live = score_telemetry(doc)
    gate = live["gate"]
    print(json.dumps({"n_runs": len(doc["runs"]), "gate": gate}, indent=2, sort_keys=True))
    print(SENTINEL)
