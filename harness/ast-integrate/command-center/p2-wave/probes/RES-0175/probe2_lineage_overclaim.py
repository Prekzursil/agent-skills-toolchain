#!/usr/bin/env python3
"""Probe 2: snapshot re-hash + overclaim mutants. Does not re-run probe1's mutant helper as the pass condition.

Re-hashes HTTP 200 snapshots against LINEAGE.json, recomputes the matrix,
and REFUSES an artifact that names instruction-stripping as the winner or
that folds mention false positives into catch_rate_neutralised.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import engine as E  # noqa: E402

SENTINEL = E.SENTINEL
LINEAGE = E.LINEAGE


def fail(msg: str) -> int:
    print(f"FAILED:RES-0175-probe2 {msg}")
    return 1


def overclaim_reasons(doc: dict) -> list[str]:
    reasons: list[str] = []
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        reasons.append(f"self-declared:{st}")
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        reasons.append("sentinel-absent")
    by = (doc.get("measured") or {}).get("by_filter") or {}
    strip = by.get("instruction_stripping") or {}
    quar = by.get("structural_quarantine") or {}
    if doc.get("answer", {}).get("winner") == "instruction_stripping":
        reasons.append("winner-is-stripping")
    if float(strip.get("catch_rate_neutralised") or 0) >= float(quar.get("catch_rate_neutralised") or 0) and quar:
        if strip.get("catch_rate_neutralised") == quar.get("catch_rate_neutralised") == 1:
            reasons.append("strip-claimed-perfect")
    if strip.get("catch_rate_neutralised") == 1 and strip.get("mentions_mangled", 0) > 0:
        reasons.append("strip-perfect-despite-mangle")
    nd = doc.get("neutralised_vs_merely_detected") or {}
    if nd.get("false_positives_counted_separately") is not True:
        reasons.append("fp-folded-into-catch")
    # Catch rate must not be (neut+merely)/n — merely-detected is not a catch.
    tag = by.get("provenance_tagging") or {}
    if tag.get("catch_rate_neutralised") == 1 and tag.get("merely_detected") == 30:
        reasons.append("tag-catch-counts-merely-detected")
    claims = doc.get("claims") or []
    if len(claims) < 3:
        reasons.append("claims<3")
    for c in claims:
        if len(c.get("signals") or []) < 2:
            reasons.append(f"{c.get('claim_id')}:single-signal")
        lin = c.get("source_lineage") or []
        if len(lin) < 1:
            reasons.append(f"{c.get('claim_id')}:no-lineage")
        for row in lin:
            if not row.get("resolved_url") or not row.get("sha256") or not row.get("fetch_timestamp"):
                reasons.append(f"{c.get('claim_id')}:lineage-incomplete")
        if not (c.get("sherman_kent") or c.get("confidence_band")):
            reasons.append(f"{c.get('claim_id')}:no-kent")
        if not (c.get("named_settling_probe") or c.get("independent_verification_path")):
            reasons.append(f"{c.get('claim_id')}:no-probe")
    return reasons


def main() -> int:
    if not E.ARTIFACT.is_file():
        return fail("artifact-absent")
    art = json.loads(E.ARTIFACT.read_text(encoding="utf-8"))
    if SENTINEL not in E.ARTIFACT.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if not LINEAGE.is_file():
        return fail("lineage-absent")
    lin = json.loads(LINEAGE.read_text(encoding="utf-8"))
    rows = [s for s in (lin.get("sources") or []) if s.get("present") is True]
    if len(rows) < 6:
        return fail(f"present-sources:{len(rows)}")

    hashed = 0
    for rec in rows:
        if rec.get("http_status") != 200:
            return fail(f"http:{rec.get('file')}:{rec.get('http_status')}")
        path = E.REPO / rec["path"]
        if not path.is_file():
            return fail(f"missing-snapshot:{rec.get('file')}")
        live = E.sha256_file(path)
        if live != rec.get("sha256"):
            return fail(f"sha-mismatch:{rec.get('file')}")
        if path.stat().st_size != rec.get("bytes"):
            return fail(f"bytes-mismatch:{rec.get('file')}")
        hashed += 1

    art_src = {
        s.get("file"): s
        for s in (art.get("source_lineage") or [])
        if isinstance(s, dict) and s.get("file")
    }
    for rec in rows:
        a = art_src.get(rec["file"])
        if not isinstance(a, dict):
            return fail(f"artifact-source-missing:{rec['file']}")
        if a.get("sha256") != rec["sha256"]:
            return fail(f"artifact-source-sha:{rec['file']}")

    docs = C.all_docs()
    live = E.run_matrix(docs)
    art_by = (art.get("measured") or {}).get("by_filter") or {}
    for name in E.FILTERS:
        if name not in art_by:
            return fail(f"filter-absent:{name}")
        for key in ("neutralised", "merely_detected", "missed", "false_positives", "catch_rate_neutralised"):
            if art_by[name].get(key) != live["by_filter"][name].get(key):
                return fail(f"drift:{name}:{key}")

    honest = overclaim_reasons(art)
    if honest:
        return fail("overclaim:" + ",".join(honest))

    mutant = copy.deepcopy(art)
    mutant["answer"]["winner"] = "instruction_stripping"
    mutant["measured"]["by_filter"]["instruction_stripping"]["catch_rate_neutralised"] = 1.0
    mutant["measured"]["by_filter"]["instruction_stripping"]["neutralised"] = 30
    fake = overclaim_reasons(mutant)
    if "winner-is-stripping" not in fake and "strip-perfect-despite-mangle" not in fake:
        return fail(f"overclaim-detector-mute:{fake}")

    design = art.get("design_table") or []
    if len(design) < 4:
        return fail(f"design_table={len(design)}")

    print(
        json.dumps(
            {
                "probe": "probe2-lineage-overclaim",
                "snapshots_hashed": hashed,
                "overclaim_live": honest,
                "overclaim_mutant_fired": True,
                "winner": art.get("answer", {}).get("winner"),
            },
            sort_keys=True,
        )
    )
    print(
        f"snapshots_hashed={hashed} winner={art.get('answer', {}).get('winner')} "
        f"overclaim_mutant_fired=True"
    )
    print("SUCCESS:RES-0175-probe2 lineage re-hash and overclaim control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
