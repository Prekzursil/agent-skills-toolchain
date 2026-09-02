"""Build the CNF-0007 confirmer assignment matrix.

A confirmer is cross-vendor independent only when implementer_vendor !=
confirmer_vendor. Same-vendor rows are labelled correlated-confirmation,
never independent. CLAIM-REGISTRY.json is used when present; otherwise the
measurable frame is every catalog work unit's assigned implementer vendor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
REGISTRY = REPO / "command-center" / "CLAIM-REGISTRY.json"

OTHER_VENDOR = {"anthropic": "openai", "openai": "anthropic"}
OTHER_MODEL = {"anthropic": "gpt-5-codex", "openai": "opus"}
P0_P1 = frozenset({"P0", "P1"})

PLANTS: list[dict[str, Any]] = [
    {
        "claim_id": "PLANT-P0-SAME-VENDOR",
        "severity": "P0",
        "row_kind": "planted-control",
        "implementer_vendor": "anthropic",
        "implementer_model": "opus",
        "implementer_role": "implementer",
        "confirmer_vendor": "anthropic",
        "confirmer_model": "opus",
        "force_same_vendor": True,
    },
    {
        "claim_id": "PLANT-P0-CROSS-VENDOR",
        "severity": "P0",
        "row_kind": "planted-control",
        "implementer_vendor": "anthropic",
        "implementer_model": "opus",
        "implementer_role": "implementer",
        "force_same_vendor": False,
    },
    {
        "claim_id": "PLANT-P0-SEVERED-STREAM",
        "severity": "P0",
        "row_kind": "planted-control",
        "implementer_vendor": "openai",
        "implementer_model": "gpt-5-codex",
        "implementer_role": "implementer",
        "force_same_vendor": False,
    },
    {
        "claim_id": "PLANT-P0-INLINE-PROMPT",
        "severity": "P0",
        "row_kind": "planted-control",
        "implementer_vendor": "openai",
        "implementer_model": "gpt-5-codex",
        "implementer_role": "implementer",
        "force_same_vendor": False,
    },
]


def classify(implementer: str, confirmer: str) -> tuple[str, bool]:
    impl = (implementer or "").strip().lower()
    conf = (confirmer or "").strip().lower()
    if not impl or not conf or impl == conf:
        return "correlated-confirmation", False
    return "independent", True


def assign_confirmer(implementer_vendor: str, force_same_vendor: bool = False) -> tuple[str, str]:
    impl = (implementer_vendor or "").strip().lower()
    if force_same_vendor:
        return impl or "anthropic", (
            "opus" if (impl or "anthropic") == "anthropic" else "gpt-5-codex"
        )
    other = OTHER_VENDOR.get(impl)
    if other is None:
        other = "openai" if impl != "openai" else "anthropic"
    return other, OTHER_MODEL[other]


def _row(
    claim_id: str,
    row_kind: str,
    implementer_vendor: str,
    implementer_model: str,
    implementer_role: str,
    confirmer_vendor: str,
    confirmer_model: str,
    severity: str | None,
) -> dict[str, Any]:
    klass, cross = classify(implementer_vendor, confirmer_vendor)
    return {
        "claim_id": claim_id,
        "severity": severity,
        "row_kind": row_kind,
        "implementer_vendor": implementer_vendor,
        "implementer_model": implementer_model,
        "implementer_role": implementer_role,
        "confirmer_vendor": confirmer_vendor,
        "confirmer_model": confirmer_model,
        "independence_class": klass,
        "vendor_pair_cross": cross,
    }


def load_registry_p0_p1() -> tuple[bool, list[dict[str, Any]]]:
    if not REGISTRY.is_file() or REGISTRY.stat().st_size <= 0:
        return False, []
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    claims = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(claims, list):
        return True, []
    out: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        sev = str(claim.get("severity") or "").upper()
        if sev not in P0_P1:
            continue
        impl_v = str(
            claim.get("implementer_vendor")
            or (claim.get("implementer") or {}).get("vendor")
            or ""
        ).lower()
        impl_m = str(
            claim.get("implementer_model")
            or (claim.get("implementer") or {}).get("model")
            or ""
        )
        cid = str(claim.get("id") or claim.get("claim_id") or "")
        if not cid or not impl_v:
            continue
        conf_v, conf_m = assign_confirmer(impl_v, False)
        out.append(
            _row(
                cid,
                "claim-registry",
                impl_v,
                impl_m,
                str(claim.get("implementer_role") or "implementer"),
                conf_v,
                conf_m,
                sev,
            )
        )
    out.sort(key=lambda r: r["claim_id"])
    return True, out


def load_catalog_frame() -> list[dict[str, Any]]:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc.get("work_units") or []
    out: list[dict[str, Any]] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        amvr = unit.get("assigned_model_vendor_role") or {}
        if not uid or not isinstance(amvr, dict):
            continue
        impl_v = str(amvr.get("vendor") or "").lower()
        if not impl_v:
            continue
        conf_v, conf_m = assign_confirmer(impl_v, False)
        out.append(
            _row(
                uid,
                "catalog-implementer-frame",
                impl_v,
                str(amvr.get("model") or ""),
                str(amvr.get("role") or ""),
                conf_v,
                conf_m,
                None,
            )
        )
    out.sort(key=lambda r: r["claim_id"])
    return out


def load_plants() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for plant in PLANTS:
        conf_v, conf_m = assign_confirmer(
            plant["implementer_vendor"], bool(plant.get("force_same_vendor"))
        )
        if plant.get("confirmer_vendor") and plant.get("force_same_vendor"):
            conf_v = plant["confirmer_vendor"]
            conf_m = plant.get("confirmer_model") or conf_m
        out.append(
            _row(
                plant["claim_id"],
                plant["row_kind"],
                plant["implementer_vendor"],
                plant["implementer_model"],
                plant["implementer_role"],
                conf_v,
                conf_m,
                plant["severity"],
            )
        )
    return out


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Assignments live under report when receipt_core forbids extra keys."""
    rep = doc.get("report") if isinstance(doc, dict) else None
    if isinstance(rep, dict) and isinstance(rep.get("assignments"), list):
        return rep
    return doc


def rate(rows: list[dict[str, Any]]) -> tuple[int, int, int, float]:
    n = len(rows)
    cross = sum(1 for r in rows if r.get("vendor_pair_cross") is True)
    corr = sum(
        1 for r in rows if r.get("independence_class") == "correlated-confirmation"
    )
    return n, cross, corr, (cross / n if n else 0.0)


def build() -> dict[str, Any]:
    registry_present, registry_rows = load_registry_p0_p1()
    plants = load_plants()
    catalog_rows = load_catalog_frame()
    labelled = list(registry_rows) + list(plants)
    n_lab, x_lab, c_lab, r_lab = rate(labelled)
    n_cat, x_cat, _c_cat, r_cat = rate(catalog_rows)
    same_independent = [
        r["claim_id"]
        for r in (labelled + catalog_rows)
        if r["implementer_vendor"] == r["confirmer_vendor"]
        and r["independence_class"] == "independent"
    ]
    if same_independent:
        raise SystemExit(
            "FAILED:CNF-0007 same-vendor row labelled independent: "
            + ",".join(same_independent)
        )
    return {
        "registry_present": registry_present,
        "registry_rows": registry_rows,
        "plants": plants,
        "catalog_rows": catalog_rows,
        "labelled": labelled,
        "assignments": catalog_rows + plants,
        "measured": {
            "n_catalog_frame": n_cat,
            "n_catalog_cross_vendor": x_cat,
            "catalog_cross_vendor_rate": r_cat,
            "n_labelled_p0_p1": n_lab,
            "n_labelled_cross_vendor": x_lab,
            "n_labelled_correlated": c_lab,
            "labelled_cross_vendor_rate": r_lab,
            "formula": (
                "cross_vendor_rate = count(implementer_vendor != confirmer_vendor) "
                "/ n; same-vendor rows are correlated-confirmation, not independent"
            ),
        },
    }
