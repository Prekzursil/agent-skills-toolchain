"""Build matched cases, gold/bad fixtures, and live oracle proofs for WFA-0112."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from families import FAMILIES, MIN_BYTES
from oracle import evaluate, evaluate_twice

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
REL_FIX = "command-center/p2-wave/probes/WFA-0112/fixtures"


def canonical(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def case_id_for(family_id: str) -> str:
    return f"{family_id}-case-01"


def gold_doc(family: dict[str, Any]) -> dict[str, Any]:
    fid = str(family["family_id"])
    body: dict[str, Any] = {
        "family_id": fid,
        "case_id": case_id_for(fid),
        "family_label": family["label"],
        "construct": family["construct"],
        "network_used": False,
        "network_required": False,
        "oracle_kind": "on-disk-postcondition",
        "min_bytes": MIN_BYTES,
    }
    body.update(family["gold"])
    return body


def mutant_blobs(family: dict[str, Any]) -> list[tuple[str, bytes]]:
    fid = str(family["family_id"])
    cid = case_id_for(fid)
    good = gold_doc(family)
    rows: list[tuple[str, bytes]] = [
        ("empty", b""),
        ("braces", b"{}\n"),
    ]
    wrong_family = dict(good)
    wrong_family["family_id"] = "D1" if fid != "D1" else "D2"
    rows.append(("wrong-family", canonical(wrong_family).encode("utf-8")))
    missing = dict(good)
    first_path = str(family["checks"][0][0]).split(".")[0]
    missing.pop(first_path, None)
    rows.append(("missing-field", canonical(missing).encode("utf-8")))
    wrong_case = dict(good)
    wrong_case["case_id"] = "not-this-case"
    rows.append(("wrong-case", canonical(wrong_case).encode("utf-8")))
    net = dict(good)
    net["network_used"] = True
    rows.append(("network-flag", canonical(net).encode("utf-8")))
    rows.append(("truncated", canonical(good).encode("utf-8")[:-12]))
    identity_only = {
        "family_id": fid,
        "case_id": cid,
        "network_used": False,
        "oracle_kind": "on-disk-postcondition",
        "padding": "x" * 80,
    }
    rows.append(("identity-only", canonical(identity_only).encode("utf-8")))
    return rows


def mutant_filename(name: str) -> str:
    if name in {"empty", "truncated"}:
        return f"bad-{name}.bin"
    return f"bad-{name}.json"


def write_fixtures() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for family in FAMILIES:
        fid = str(family["family_id"])
        d = FIXTURES / fid
        d.mkdir(parents=True, exist_ok=True)
        (d / "good.json").write_text(canonical(gold_doc(family)), encoding="utf-8")
        for name, blob in mutant_blobs(family):
            (d / mutant_filename(name)).write_bytes(blob)


def prove() -> dict[str, Any]:
    write_fixtures()
    cases: list[dict[str, Any]] = []
    det_ok = True
    reject_ok = True
    cross_ok = True
    for family in FAMILIES:
        fid = str(family["family_id"])
        cid = case_id_for(fid)
        good = FIXTURES / fid / "good.json"
        twice = evaluate_twice(good, fid, cid)
        gold_accept = bool(twice["first"]["accept"])
        if not twice["identical"] or not gold_accept:
            det_ok = False
        mutant_proofs = []
        for name, _blob in mutant_blobs(family):
            path = FIXTURES / fid / mutant_filename(name)
            v = evaluate(path, fid, cid)
            if v["accept"]:
                reject_ok = False
            mutant_proofs.append(
                {
                    "name": name,
                    "accept": v["accept"],
                    "reasons": v["reasons"],
                    "path": f"{REL_FIX}/{fid}/{mutant_filename(name)}",
                }
            )
        cross = []
        for other in FAMILIES:
            oid = str(other["family_id"])
            if oid == fid:
                continue
            v = evaluate(good, oid, case_id_for(oid))
            if v["accept"]:
                cross_ok = False
            cross.append({"other_family": oid, "accept": v["accept"]})
        cases.append(
            {
                "family_id": fid,
                "family_label": family["label"],
                "construct": family["construct"],
                "case_id": cid,
                "status": "COVERED",
                "network_required": False,
                "gold_path": f"{REL_FIX}/{fid}/good.json",
                "oracle": {
                    "kind": "on-disk-postcondition",
                    "pattern": (
                        "packaged-artifact-smoke: exists, min-bytes, UTF-8 JSON "
                        "object, identity, construct fields"
                    ),
                    "double_run_identical": twice["identical"],
                    "gold_accept": gold_accept,
                    "gold_reasons": twice["first"]["reasons"],
                    "gold_bytes": twice["first"].get("bytes"),
                },
                "known_bad": mutant_proofs,
                "cross_family_rejects": cross,
            }
        )
    family_rows = [
        {
            "family_id": str(family["family_id"]),
            "label": family["label"],
            "construct": family["construct"],
            "label_source": "stand-in: catalog ids D1-D20; library file absent",
            "case_id": case_id_for(str(family["family_id"])),
            "coverage": "COVERED",
        }
        for family in FAMILIES
    ]
    return {
        "cases": cases,
        "families": family_rows,
        "uncovered_families": [],
        "proofs": {
            "all_oracles_deterministic": det_ok,
            "all_known_bad_rejected": reject_ok,
            "cross_family_gold_rejected": cross_ok,
            "n_families": len(FAMILIES),
            "n_covered": len(cases),
            "n_uncovered": 0,
        },
        "repo": str(REPO),
    }
