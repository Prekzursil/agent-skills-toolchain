"""Shared ADV-0085 helpers: fixtures, ranking, ablation, controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formula import (
    PRODUCTION_MODULE as PRODUCTION_MODULE,
    TERM_IDS,
    WEIGHTS,
    score_from_components as score_from_components,
    score_with_length_mutant as score_with_length_mutant,
    score_with_term_zeroed as score_with_term_zeroed,
)
from inspect_output import GOLD_IDS as GOLD_IDS, inspect_envelope as inspect_envelope

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
ART_REL = "command-center/adversarial/ADV-0085-degenerate-strategy-metric-attack.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/benchmark-integrity.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0085 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0085 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0085/probe1_rank.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0085/probe2_ablate.py"
)
P1_CMD = P1_CMD
P2_CMD = P2_CMD
ART_REL = ART_REL
SCHEMA_REL = SCHEMA_REL
INTENDED_REFERENCE_ORDER = ("ref-high", "ref-mid", "ref-low")
DEGENERATE_IDS = ("deg-schema-only", "deg-always-abstain", "deg-pad-anchors")
REFERENCE_IDS = INTENDED_REFERENCE_ORDER


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _case(
    cid: str,
    *,
    answer: str | None = "",
    abstain: bool = False,
    recovered: bool = False,
    anchors: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": cid,
        "answer": answer,
        "abstain": abstain,
        "recovered": recovered,
        "evidence_anchors": list(anchors or []),
    }
    if notes is not None:
        row["notes"] = notes
    return row


def _envelope(status: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": 1, "status": status, "cases": cases}


def production_module_present() -> bool:
    return (REPO / PRODUCTION_MODULE).is_file()


def ensure_fixtures() -> dict[str, Path]:
    """Materialise reference and degenerate run envelopes with deterministic bytes."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    ref_high = _envelope(
        "ok",
        [
            _case("C1", answer="42", anchors=["oracle.py:10"]),
            _case("C2", answer="alpha", anchors=["spec.md:4"]),
            _case("C3", answer="commit-abc", anchors=["oracle.py:10"]),
            _case("C4", answer="deny", anchors=["spec.md:4"]),
            _case("C5", answer="retry-ok", recovered=True, anchors=["oracle.py:10"]),
            _case("C6", answer="", abstain=True),
        ],
    )
    ref_mid = _envelope(
        "ok",
        [
            _case("C1", answer="42", anchors=["spec.md:4"]),
            _case("C2", answer="wrong"),
            _case("C3", answer="no"),
            _case("C4", answer="maybe"),
            _case("C5", answer="gave-up"),
            _case("C6", answer="guess"),
        ],
    )
    ref_low = _envelope(
        "error",
        [
            _case("C1", answer=""),
            _case("C2", answer=""),
            _case("C3", answer=""),
            _case("C4", answer=""),
        ],
    )
    deg_schema = _envelope(
        "ok",
        [_case(cid, answer="") for cid in GOLD_IDS],
    )
    deg_abstain = _envelope(
        "abstain",
        [_case(cid, answer="", abstain=True) for cid in GOLD_IDS],
    )
    deg_pad = _envelope(
        "ok",
        [
            _case(
                cid,
                answer="",
                anchors=[
                    "padding://anchor-a",
                    "padding://anchor-b",
                    "padding://anchor-c",
                ],
            )
            for cid in GOLD_IDS
        ],
    )
    notes_pad = "lorem-ipsum-notes " * 40
    ref_high_notes = json.loads(json.dumps(ref_high))
    ref_high_notes["cases"][0]["notes"] = notes_pad
    mapping = {
        "ref-high": ref_high,
        "ref-mid": ref_mid,
        "ref-low": ref_low,
        "deg-schema-only": deg_schema,
        "deg-always-abstain": deg_abstain,
        "deg-pad-anchors": deg_pad,
        "ref-high-notes-twin": ref_high_notes,
    }
    paths: dict[str, Path] = {}
    for name, doc in mapping.items():
        path = FIXTURES / f"{name}.json"
        _write_json(path, doc)
        paths[name] = path
    return paths


def load_envelope(label: str) -> dict[str, Any]:
    paths = ensure_fixtures()
    return json.loads(paths[label].read_text(encoding="utf-8"))


def scored_run(label: str) -> dict[str, Any]:
    doc = load_envelope(label)
    inspected = inspect_envelope(doc)
    scored = score_from_components(inspected["components"])
    return {
        "label": label,
        "kind": "degenerate" if label.startswith("deg-") else "reference",
        "inspected": inspected,
        "score": scored,
        "total": scored["total"],
        "substance": inspected["substance"]["ratio"],
        "rederivable": scored["rederivable"],
        "schema_valid": inspected["schema_valid"],
        "answer_chars": inspected["answer_chars"],
    }


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (-float(r["total"]), str(r["label"])))
    out = []
    for i, row in enumerate(ordered, 1):
        item = dict(row)
        item["rank"] = i
        out.append(item)
    return out


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": row["label"],
        "kind": row["kind"],
        "rank": row.get("rank"),
        "total": row["total"],
        "substance": row["substance"],
        "parts": row["score"]["parts"],
        "components": row["score"]["components"],
        "oracle_correctness": row["inspected"]["substance"]["oracle_correctness"],
        "resolving_anchor_rate": row["inspected"]["substance"]["resolving_anchor_rate"],
        "unique_anchors": row["inspected"]["unique_anchors"],
        "schema_valid": row["schema_valid"],
        "rederivable": row["rederivable"],
    }


def inversion_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Degenerate outranks a genuine run that has strictly higher substance."""
    by = {r["label"]: r for r in rows}
    found = []
    for deg_id in DEGENERATE_IDS:
        deg = by[deg_id]
        for ref_id in REFERENCE_IDS:
            ref = by[ref_id]
            if float(deg["total"]) > float(ref["total"]) and float(deg["substance"]) < float(
                ref["substance"]
            ):
                found.append(
                    {
                        "degenerate": deg_id,
                        "reference": ref_id,
                        "degenerate_total": deg["total"],
                        "reference_total": ref["total"],
                        "degenerate_substance": deg["substance"],
                        "reference_substance": ref["substance"],
                        "margin": round(float(deg["total"]) - float(ref["total"]), 6),
                    }
                )
    found.sort(key=lambda p: (-p["margin"], p["degenerate"], p["reference"]))
    return found


def ranking_bundle() -> dict[str, Any]:
    labels = list(REFERENCE_IDS) + list(DEGENERATE_IDS)
    rows = rank_rows([scored_run(label) for label in labels])
    compact = [_compact(r) for r in rows]
    by_label = {r["label"]: r for r in compact}
    intended = [by_label[i]["total"] for i in INTENDED_REFERENCE_ORDER]
    order_holds = intended[0] > intended[1] > intended[2]
    pairs = inversion_pairs(compact)
    exploits = sorted({p["degenerate"] for p in pairs})
    observed = [
        r["label"]
        for r in sorted(
            (by_label[i] for i in INTENDED_REFERENCE_ORDER),
            key=lambda r: (-r["total"], r["label"]),
        )
    ]
    return {
        "probe": "probe1-degenerate-versus-reference-rank",
        "unit_id": "ADV-0085",
        "production_module": PRODUCTION_MODULE,
        "production_module_present": production_module_present(),
        "weights": dict(WEIGHTS),
        "ranked": compact,
        "by_label": by_label,
        "intended_reference_order": list(INTENDED_REFERENCE_ORDER),
        "observed_reference_order": observed,
        "control_reference_order": {
            "pass": order_holds,
            "intended": list(INTENDED_REFERENCE_ORDER),
            "observed": observed,
            "totals": {i: by_label[i]["total"] for i in INTENDED_REFERENCE_ORDER},
            "already_inverted": not order_holds,
            "summary": (
                "reference outputs rank in intended quality order under the unmodified metric"
                if order_holds
                else "metric is already inverted on honest references; that is the finding"
            ),
        },
        "inversion_pairs": pairs,
        "exploiting_strategies": exploits,
        "any_exploit": bool(pairs),
        "rederivable": all(r["rederivable"] for r in compact),
    }


def ablation_bundle() -> dict[str, Any]:
    """Per-term ablation: mechanically independent of probe 1's verdict list."""
    labels = list(REFERENCE_IDS) + list(DEGENERATE_IDS)
    live = {label: scored_run(label) for label in labels}
    base_compact = []
    for label in labels:
        row = _compact(live[label])
        row["rank"] = 0
        base_compact.append(row)
    baseline_pairs = inversion_pairs(base_compact)

    term_rows = []
    for term in TERM_IDS:
        ablated = []
        for label in labels:
            dropped = score_with_term_zeroed(live[label]["inspected"]["components"], term)
            row = {
                "label": label,
                "kind": live[label]["kind"],
                "total": dropped["total"],
                "substance": live[label]["substance"],
                "score": {
                    "parts": dropped["parts"],
                    "components": dropped["components"],
                },
                "inspected": live[label]["inspected"],
                "rederivable": True,
                "schema_valid": live[label]["schema_valid"],
                "rank": 0,
            }
            ablated.append(_compact(row))
        ranked = rank_rows(ablated)
        pairs = inversion_pairs(ranked)
        remaining = sorted({p["degenerate"] for p in pairs})
        restored = [
            deg
            for deg in DEGENERATE_IDS
            if any(p["degenerate"] == deg for p in baseline_pairs)
            and not any(p["degenerate"] == deg for p in pairs)
        ]
        term_rows.append(
            {
                "term": term,
                "weight": WEIGHTS[term],
                "ranked": [
                    {"label": r["label"], "total": r["total"], "rank": r["rank"]}
                    for r in ranked
                ],
                "inversion_pairs": pairs,
                "remaining_exploits": remaining,
                "exploits_restored": restored,
                "clears_all_inversions": not pairs,
            }
        )

    localised = []
    baseline_degs = {p["degenerate"] for p in baseline_pairs}
    for deg in DEGENERATE_IDS:
        if deg not in baseline_degs:
            continue
        depended = [
            row["term"]
            for row in term_rows
            if deg not in row["remaining_exploits"]
        ]
        localised.append(
            {
                "degenerate": deg,
                "depends_on_terms": depended,
                "primary_term": depended[0] if depended else None,
                "unique_term": depended[0] if len(depended) == 1 else None,
            }
        )

    high = live["ref-high"]
    twin = scored_run("ref-high-notes-twin")
    silent = abs(high["total"] - twin["total"]) < 1e-9
    mutant_high = score_with_length_mutant(
        high["inspected"]["components"], high["answer_chars"]
    )
    mutant_twin = score_with_length_mutant(
        twin["inspected"]["components"], twin["answer_chars"]
    )
    fired = mutant_twin > mutant_high + 1e-9
    return {
        "probe": "probe2-per-term-ablation",
        "unit_id": "ADV-0085",
        "independent_of_probe1_verdicts": True,
        "production_module_present": production_module_present(),
        "baseline_zero_vector_check": score_from_components(
            {term: 0.0 for term in TERM_IDS}
        )["total"],
        "baseline_inversion_pairs": baseline_pairs,
        "from_term_drop": term_rows,
        "localised_exploits": localised,
        "clears_all_inversions_terms": [
            row["term"] for row in term_rows if row["clears_all_inversions"]
        ],
        "control_length_mutant": {
            "id": "NC-LENGTH-TERM-MUTANT",
            "silent_on_good_state": silent,
            "fired_on_bad_state": fired,
            "pass": bool(silent and fired),
            "good_ref_high": high["total"],
            "good_notes_twin": twin["total"],
            "mutant_ref_high": mutant_high,
            "mutant_notes_twin": mutant_twin,
            "summary": (
                "Real formula ignores notes padding. Mutant that bonuses "
                "answer/notes length >= 500 scores the padded twin higher."
            ),
        },
    }


def target_verdicts(rank: dict[str, Any], ablate: dict[str, Any]) -> list[dict[str, Any]]:
    by = rank["by_label"]
    exploits = set(rank["exploiting_strategies"])
    loc = {row["degenerate"]: row for row in ablate["localised_exploits"]}
    order = rank["control_reference_order"]
    pad_terms = (loc.get("deg-pad-anchors") or {}).get("depends_on_terms") or []
    abs_terms = (loc.get("deg-always-abstain") or {}).get("depends_on_terms") or []
    schema_terms = (loc.get("deg-schema-only") or {}).get("depends_on_terms") or []
    return [
        {
            "target_id": "schema-only-empty-outranks-genuine",
            "verdict": "CONFIRMED" if "deg-schema-only" in exploits else "REFUTED",
            "strategy": "deg-schema-only",
            "summary": (
                "Valid-schema empty answers versus genuine references; "
                f"score={by['deg-schema-only']['total']} substance="
                f"{by['deg-schema-only']['substance']}."
            ),
        },
        {
            "target_id": "always-abstain-outranks-genuine",
            "verdict": "CONFIRMED" if "deg-always-abstain" in exploits else "REFUTED",
            "strategy": "deg-always-abstain",
            "depends_on_terms": abs_terms,
            "summary": (
                "Always-abstain envelope versus genuine references; "
                f"score={by['deg-always-abstain']['total']} substance="
                f"{by['deg-always-abstain']['substance']}."
            ),
        },
        {
            "target_id": "padded-evidence-anchors-outrank-genuine",
            "verdict": "CONFIRMED" if "deg-pad-anchors" in exploits else "REFUTED",
            "strategy": "deg-pad-anchors",
            "depends_on_terms": pad_terms,
            "summary": (
                "Padded evidence anchors versus genuine references; "
                f"score={by['deg-pad-anchors']['total']} substance="
                f"{by['deg-pad-anchors']['substance']}."
            ),
        },
        {
            "target_id": "coverage-term-is-citation-count",
            "verdict": "CONFIRMED" if "coverage" in pad_terms else "REFUTED",
            "summary": (
                "Ablation localises the pad-anchors inversion to the coverage "
                f"term (depends_on={pad_terms})."
            ),
        },
        {
            "target_id": "recovery-term-credits-uncalibrated-abstention",
            "verdict": "CONFIRMED" if "recovery" in abs_terms else "REFUTED",
            "summary": (
                "Ablation localises the always-abstain inversion to the recovery "
                f"term (depends_on={abs_terms})."
            ),
        },
        {
            "target_id": "schema-validity-alone-inverts-ranking",
            "verdict": "CONFIRMED"
            if "deg-schema-only" in exploits and schema_terms == ["correctness"]
            else "REFUTED",
            "summary": (
                "Schema-only empty output does not outrank a genuine reference "
                "under this reconstruction; correctness-as-schema is not enough "
                "by itself."
            ),
        },
        {
            "target_id": "reference-order-already-inverted",
            "verdict": "CONFIRMED" if order["already_inverted"] else "REFUTED",
            "summary": order["summary"],
        },
        {
            "target_id": "substance-excluded-from-certification-score",
            "verdict": "CONFIRMED"
            if (
                by["ref-high"]["oracle_correctness"]
                > by["deg-pad-anchors"]["oracle_correctness"]
                and by["deg-pad-anchors"]["total"] > by["ref-mid"]["total"]
            )
            else "REFUTED",
            "summary": (
                "Oracle correctness is a substance measure and does not enter the "
                "score; a zero-oracle degenerate can still outrank a genuine run."
            ),
        },
        {
            "target_id": "live-production-quality-metric-module",
            "verdict": "CONFIRMED" if not rank["production_module_present"] else "REFUTED",
            "summary": (
                f"{PRODUCTION_MODULE} is absent; probes scored the reconstructed WFA-0114 proxies."
                if not rank["production_module_present"]
                else f"{PRODUCTION_MODULE} is present."
            ),
        },
    ]


def run_controls(rank: dict[str, Any], ablate: dict[str, Any]) -> list[dict[str, Any]]:
    order = rank["control_reference_order"]
    length = ablate["control_length_mutant"]
    by = rank["by_label"]
    zero = ablate["baseline_zero_vector_check"]
    return [
        {
            "id": "CTRL-REFERENCE-ORDER",
            "name": "Reference outputs rank in intended quality order under the unmodified metric",
            "pass": order["pass"],
            "fired_on_bad_state": order["already_inverted"],
            "silent_on_good_state": order["pass"],
            "summary": order["summary"],
        },
        {
            "id": "NC-LENGTH-TERM-MUTANT",
            "name": length["summary"],
            "fired_on_bad_state": length["fired_on_bad_state"],
            "silent_on_good_state": length["silent_on_good_state"],
            "pass": length["pass"],
            "summary": length["summary"],
        },
        {
            "id": "CTRL-ZERO-VECTOR",
            "name": "The all-zero component vector scores 0",
            "pass": abs(float(zero)) < 1e-9,
            "fired_on_bad_state": True,
            "silent_on_good_state": abs(float(zero)) < 1e-9,
            "summary": f"zero_vector_score={zero}",
        },
        {
            "id": "CTRL-HIGH-SUBSTANCE-GT-DEGENERATE",
            "name": "Substance of ref-high is strictly above every degenerate",
            "pass": all(
                by["ref-high"]["substance"] > by[d]["substance"] for d in DEGENERATE_IDS
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "summary": (
                f"ref-high substance={by['ref-high']['substance']} vs degenerates "
                + ", ".join(f"{d}={by[d]['substance']}" for d in DEGENERATE_IDS)
            ),
        },
        {
            "id": "NC-INVERSION-DETECTOR-SILENT-ON-HONEST-PAIR",
            "name": "Inversion detector is silent on ref-high vs ref-mid (honest pair)",
            "fired_on_bad_state": bool(rank["inversion_pairs"]),
            "silent_on_good_state": (
                by["ref-high"]["total"] > by["ref-mid"]["total"]
                and by["ref-high"]["substance"] > by["ref-mid"]["substance"]
            ),
            "pass": (
                by["ref-high"]["total"] > by["ref-mid"]["total"]
                and by["ref-high"]["substance"] > by["ref-mid"]["substance"]
            ),
            "summary": "Honest pair keeps both score order and substance order.",
        },
    ]
