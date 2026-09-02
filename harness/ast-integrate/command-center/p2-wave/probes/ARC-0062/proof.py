"""Mechanical proof: reconciliation + single-evaluator coverage + bypass plant."""
from __future__ import annotations

from typing import Any

from hybrid import FORBIDDEN_GRANT_NODES, SINGLE_EVALUATOR_NODE, drop_path, hybrid_paths
from sources import EPOCHS, source_dossier_paths

PLANT_ID = "PLANT.bypass.marketplace-skip-evaluator"
PLANT_SECOND_GRANT_ID = "PLANT.bypass.marketplace-local-acl"


def plant_skip_evaluator() -> dict[str, Any]:
    """Synthetic marketplace path that verifies a signature then executes."""
    return {
        "id": PLANT_ID,
        "source_architecture": "PLANT",
        "source_unit": "ARC-0062",
        "epoch": "install-time",
        "arrival": "marketplace",
        "effect": "execute_package_bytes",
        "plane_checks": ["marketplace_signature_verify"],
        "hops": [
            "arrival_marketplace",
            "marketplace_signature_verify",
            "execute_package_bytes",
        ],
        "crosses_single_evaluator": False,
        "binding": "synthetic-bypass-plant",
    }


def plant_second_grant() -> dict[str, Any]:
    """Synthetic path whose grant authority is marketplace_acl, not the choke."""
    return {
        "id": PLANT_SECOND_GRANT_ID,
        "source_architecture": "PLANT",
        "source_unit": "ARC-0062",
        "epoch": "dispatch-time",
        "arrival": "marketplace",
        "effect": "run_installed_package",
        "plane_checks": ["marketplace_acl"],
        "hops": [
            "arrival_marketplace",
            "marketplace_acl",
            "run_installed_package",
        ],
        "crosses_single_evaluator": False,
        "binding": "synthetic-second-grant-plant",
    }


def findings_for(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every path that bypasses the single evaluator or uses a second grant."""
    found: list[dict[str, Any]] = []
    for row in paths:
        hops = [str(h) for h in (row.get("hops") or [])]
        reasons: list[str] = []
        if SINGLE_EVALUATOR_NODE not in hops:
            reasons.append("missing-evaluator")
        n_eval = hops.count(SINGLE_EVALUATOR_NODE)
        if n_eval > 1:
            reasons.append("duplicate-evaluator-node")
        second = sorted(FORBIDDEN_GRANT_NODES.intersection(hops))
        if second:
            reasons.append("second-grant:" + ",".join(second))
        if reasons:
            found.append(
                {
                    "id": row.get("id"),
                    "epoch": row.get("epoch"),
                    "arrival": row.get("arrival"),
                    "hops": hops,
                    "reasons": reasons,
                }
            )
    found.sort(key=lambda r: str(r.get("id") or ""))
    return found


def reconcile(
    source_paths: list[dict[str, Any]] | None = None,
    composed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """source dossier ids minus hybrid ids. Must be empty (computed, not asserted)."""
    src = source_paths if source_paths is not None else source_dossier_paths()
    hyb = composed if composed is not None else hybrid_paths()
    src_ids = {str(r["id"]) for r in src}
    hyb_ids = {str(r["id"]) for r in hyb}
    missing = sorted(src_ids - hyb_ids)
    extra = sorted(hyb_ids - src_ids)
    return {
        "computed": True,
        "source_count": len(src_ids),
        "hybrid_count": len(hyb_ids),
        "missing": missing,
        "missing_count": len(missing),
        "hybrid_extra_vs_source_dossiers": extra,
        "empty_minuend": missing == [],
    }


def epoch_coverage(paths: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = paths if paths is not None else hybrid_paths()
    present = {str(r.get("epoch") or "") for r in rows}
    missing = [e for e in EPOCHS if e not in present]
    by_epoch = {e: 0 for e in EPOCHS}
    for r in rows:
        ep = str(r.get("epoch") or "")
        if ep in by_epoch:
            by_epoch[ep] += 1
    return {
        "required": list(EPOCHS),
        "present": sorted(present),
        "missing": missing,
        "counts": by_epoch,
        "complete": missing == [],
    }


def prove_clean() -> dict[str, Any]:
    paths = hybrid_paths()
    rec = reconcile(composed=paths)
    cov = epoch_coverage(paths)
    bypass = findings_for(paths)
    return {
        "path_count": len(paths),
        "reconciliation": rec,
        "epochs": cov,
        "bypass_findings": bypass,
        "bypass_count": len(bypass),
        "clean": rec["empty_minuend"] and cov["complete"] and bypass == [],
    }


def prove_plant(plant: dict[str, Any] | None = None) -> dict[str, Any]:
    planted = plant if plant is not None else plant_skip_evaluator()
    paths = hybrid_paths() + [planted]
    bypass = findings_for(paths)
    caught = any(str(f.get("id")) == str(planted["id"]) for f in bypass)
    return {
        "plant_id": planted["id"],
        "plant_hops": planted["hops"],
        "findings": bypass,
        "finding_count": len(bypass),
        "caught": caught,
    }


def prove_reconciliation_both_states() -> dict[str, Any]:
    """Known-present path is in the minuend; dropping it from hybrid must surface."""
    src = source_dossier_paths()
    hyb = hybrid_paths()
    clean = reconcile(src, hyb)
    victim = "A3.install.package-content"
    mutant = reconcile(src, drop_path(hyb, victim))
    return {
        "victim": victim,
        "clean_missing": clean["missing"],
        "mutant_missing": mutant["missing"],
        "clean_empty": clean["empty_minuend"] is True,
        "mutant_reports_victim": victim in mutant["missing"],
        "discriminates": clean["empty_minuend"] is True
        and victim in mutant["missing"],
    }


def run_proof() -> dict[str, Any]:
    clean = prove_clean()
    skip = prove_plant(plant_skip_evaluator())
    second = prove_plant(plant_second_grant())
    both = prove_reconciliation_both_states()
    ok = (
        clean["clean"] is True
        and skip["caught"] is True
        and second["caught"] is True
        and both["discriminates"] is True
    )
    return {
        "ok": ok,
        "evaluator_node": SINGLE_EVALUATOR_NODE,
        "clean": clean,
        "plant_skip": skip,
        "plant_second_grant": second,
        "reconciliation_both_states": both,
    }
