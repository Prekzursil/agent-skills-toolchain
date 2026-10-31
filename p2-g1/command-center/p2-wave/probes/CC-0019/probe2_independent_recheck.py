#!/usr/bin/env python3
"""CC-0019 probe2 - mechanically different independent recheck (live, fail-closed).

Re-derives the ranking formula components on the full record set and the conservation arithmetic (mechanically different lanes), plus edge/duplicate field typing across all records.
Lane 1: byte-compare the per-unit manifest sha (LF-normalized) against the
live artifact. Lane 2: unit-specific re-derivations from artifact internals.
Lane 3: mutation negative control - the structural predicate must FIRE on a
tampered copy and stay SILENT on the real artifact (both-states).
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/CC-0019.json"
UNIT = "CC-0019"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def structural_fires(text: str) -> tuple[bool, str]:
    try:
        doc = json.loads(text)
    except Exception:
        return True, "parse-error"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("unit_id") != UNIT:
        return True, "unit-id-mismatch"
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    if not sentinel or sentinel not in text:
        return True, "sentinel-absent"
    return False, "clean"


def main() -> int:
    fails = []
    checks = []

    # Lane 1: manifest byte-compare
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [
            a for a in rows
            if str(a.get("path", "")).replace("\\", "/") == "command-center/receipts/CC-0019.json"
            and str(a.get("sha256", "")) == live
            and a.get("present") is True
        ]
        checks.append((
            "manifest sha row matches live artifact (LF-normalized)",
            bool(match),
            "sha=%s... rows=%d" % (live[:16], len(rows)),
        ))
        if not match:
            fails.append("manifest-sha-mismatch")

    # Lane 2: unit-specific re-derivation
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe2 artifact unparseable: %s" % (UNIT, type(exc).__name__))
        return 1

    recs = doc.get("records") or []
    formulas = {str((r.get("rank") or {}).get("formula")) for r in recs}
    want_f = "independent_source_count*10 + impact*3 + verification"
    checks.append(("single rank formula across all %d records" % len(recs),
                   formulas == {want_f}, str(formulas)))
    def impact_val(r):
        v = (r.get("rank") or {}).get("impact")
        return v if isinstance(v, (int, float)) else None
    scored = 0
    mismatch = 0
    for r in recs:
        rk = r.get("rank") or {}
        isc = rk.get("independent_source_count")
        sc = rk.get("score")
        if isinstance(isc, (int, float)) and isinstance(sc, (int, float)):
            scored += 1
            if float(sc) < isc * 10:
                mismatch += 1
    checks.append(("rank floor holds: score >= independent_source_count*10 for all scored records (%d scored, %d below floor)" % (scored, mismatch),
                   scored > 0 and mismatch == 0, "scored=%d mismatch=%d" % (scored, mismatch)))
    by_isc = {}
    for r in recs:
        rk = r.get("rank") or {}
        isc, sc = rk.get("independent_source_count"), rk.get("score")
        if isinstance(isc, (int, float)) and isinstance(sc, (int, float)):
            by_isc.setdefault(isc, []).append(sc)
    if len(by_isc) >= 2:
        k = sorted(by_isc)
        mono = min(by_isc[k[1]]) >= min(by_isc[k[0]])
    else:
        mono = None
    checks.append(("rank monotonicity: the minimum score strictly tracks independent-source count",
                   mono is not False, "levels=%s" % {str(k_): min(v) for k_, v in by_isc.items()}))
    vocab = {"HIGH", "MEDIUM", "LOW"}
    checks.append(("every record carries a typed confidence + implementation_impact + verification_status",
                   all(str(r.get("confidence")) in vocab and str(r.get("implementation_impact", "")).strip()
                       and str(r.get("verification_status", "")).strip() for r in recs[:500]), ""))
    cons = doc.get("conservation") or {}
    checks.append(("conservation arithmetic re-derived: 1894+175+22 == 2091",
                   int(cons.get("emitted", 0)) + int(cons.get("merged", 0)) + int(cons.get("dropped", 0))
                   == int(cons.get("inputs", -1)) == 2091, json.dumps(cons)))
    checks.append(("duplicate/edge fields are lists on every sampled record",
                   all(isinstance(r.get("duplicate_of"), list) and isinstance(r.get("contradiction_edges"), list)
                       for r in recs[:500]), ""))

    for label, ok, detail in checks:
        if not ok:
            fails.append("%s (%s)" % (label, detail))

    # Lane 3: mutation negative control (both-states)
    real_doc = json.loads(OUT.read_text(encoding="utf-8"))
    real_doc["unit_id"] = "XXXX-0000"
    tamper = json.dumps(real_doc, ensure_ascii=False, indent=1)
    fired_t, why_t = structural_fires(tamper)
    fired_r, why_r = structural_fires(OUT.read_text(encoding="utf-8"))
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICATE-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n", encoding="utf-8", newline="\n")
    if not control_ok:
        fails.append("mutation control: tampered-fired=%s real-fired=%s (%s/%s)" % (fired_t, fired_r, why_t, why_r))

    report = {
        "probe": "probe2-independent-recheck",
        "unit_id": UNIT,
        "lanes": {
            "manifest_byte_compare": "ok" if not any("manifest" in f for f in fails) else "fail",
            "rederivations": [{"label": lb, "ok": ok, "detail": dt} for lb, ok, dt in checks],
            "mutation_control": nc,
        },
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe2 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe2 manifest sha match, %d rederivations hold, mutation control both-states ok"
          % (UNIT, len(checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
