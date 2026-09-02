#!/usr/bin/env python3
"""Probe 2: license/credit survival and known-broken license strip.

Reads upstream LICENSE and CREDIT files (not the decompose execute path) and
requires strip-license to surface spec:11334. Also asserts the adjudicator-only
certification record was excluded from the blinding payload.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from engine import decompose, fuse_union, strip_license  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0176.json"
CERT = HERE / "fixtures/certified-fusion/certification.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0176-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0176" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    sources = S.load_sources()
    fusion = fuse_union(sources, S.FUSION_ID)
    chain = []
    for src in sources:
        repo = src["_repo"]
        lic_path = REPO / repo["path"] / "LICENSE"
        cred_path = REPO / repo["path"] / "CREDIT"
        if not lic_path.is_file() or not cred_path.is_file():
            return fail(f"upstream files missing for {src['id']}")
        lic = lic_path.read_text(encoding="utf-8")
        cred = cred_path.read_text(encoding="utf-8")
        if src["license"] not in lic and src.get("spdx", "") not in lic:
            return fail(f"LICENSE does not name {src['license']} for {src['id']}")
        if src["credit"] not in cred:
            return fail(f"CREDIT missing string {src['credit']}")
        lineage = next(
            s for s in fusion["lineage"]["sources"] if s["id"] == src["id"]
        )
        if lineage.get("license") != src["license"]:
            return fail(f"lineage license drift {src['id']}")
        if lineage.get("credit") != src["credit"]:
            return fail(f"lineage credit drift {src['id']}")
        chain.append(
            {
                "source_id": src["id"],
                "upstream_license_ok": True,
                "upstream_credit_ok": True,
                "lineage_matches": True,
                "spdx": lineage.get("spdx"),
            }
        )

    broken = strip_license(fusion, "wf-alpha")
    broken_decomp = decompose(broken)
    fired = any(
        (not r.get("license_present")) and r.get("source_id") == "wf-alpha"
        for r in broken_decomp["reports"]
    )
    if not fired:
        return fail("strip-license did not report LICENSE-ABSENT")
    intact = decompose(fusion)
    intact_ok = all(r.get("license_present") and r.get("credit_present") for r in intact["reports"])
    if not intact_ok:
        return fail("intact fusion missing license or credit after decompose")

    rec = doc.get("license_strip_control") or {}
    if rec.get("detector_fired") is not True:
        return fail("artifact license_strip_control.detector_fired is not true")

    blinding = doc.get("blinding_attestation") or doc.get("blinding") or {}
    excluded = list(blinding.get("excluded") or [])
    if S.BLIND_EXCLUDE not in excluded:
        return fail("certification.json not on blinding exclude list")
    if blinding.get("lazy_instruction_leaked") is True:
        return fail("lazy certification instruction leaked into payload")
    if not CERT.is_file():
        return fail("adjudicator-only certification.json missing on disk")
    cert = json.loads(CERT.read_text(encoding="utf-8"))
    evidence_blob = json.dumps(
        {
            "baseline_repro": doc.get("baseline_repro"),
            "corrected_repro": doc.get("corrected_repro"),
            "per_component": doc.get("per_component"),
            "tests": doc.get("tests"),
        },
        sort_keys=True,
    )
    lazy = str(cert.get("instruction_to_lazy_confirmer") or "")
    if lazy and lazy in evidence_blob:
        return fail("artifact evidence cites lazy certification instruction")

    live = S.run_confirmation()
    if live.get("blinding", {}).get("sha256") != blinding.get("hash") and live.get(
        "blinding", {}
    ).get("sha256") != blinding.get("sha256"):
        return fail("blinding attestation hash != live recompute")

    out = {
        "probe": "probe2-license-control",
        "unit_id": "CNF-0176",
        "license_chain": chain,
        "strip_detector_fired": True,
        "intact_license_credit": True,
        "blinding_excludes_certification": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for row in chain:
        print(
            f"license {row['source_id']} spdx={row['spdx']} "
            f"upstream_ok={row['upstream_license_ok']} lineage_ok={row['lineage_matches']}"
        )
    print("SUCCESS:CNF-0176-probe2 license strip and upstream LICENSE/CREDIT chain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
