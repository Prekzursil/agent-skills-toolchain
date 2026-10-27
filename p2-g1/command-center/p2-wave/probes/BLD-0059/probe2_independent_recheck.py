#!/usr/bin/env python3
"""BLD-0059 probe2 - mechanically different independent recheck (live, fail-closed).

Recomputes the power numbers through the recreated power.py instrument (mechanically different lane), the break-even reviewer time identity, and the sensitivity direction (smaller prevalence -> lower detection at fixed n).
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
OUT = REPO / "command-center/receipts/BLD-0059.json"
UNIT = "BLD-0059"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/receipts/BLD-0059.json"
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

    import importlib.util
    spec = importlib.util.spec_from_file_location("power_instr", HERE / "power.py")
    pinst = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pinst)
    acc = (((doc.get("sampling") or {}).get("acceptance_criterion") or {}).get("claimed_scheme") or {})
    n, p = int(acc.get("n", -1)), float(acc.get("prevalence", -1))
    d = pinst.detect(n, p)
    checks.append(("power.py hand-check n=14: detect = 1-(0.8)**14",
                   abs(d - float(acc.get("detection_probability", -1))) < 1e-12 and abs(d - 0.95601953488896) < 1e-9,
                   "recomputed=%.14f" % d))
    ok, d3 = pinst.accept(3, p, 0.95)
    checks.append(("reject-scheme control: n=3 at p=0.20 detects %.3f < 0.95 -> not accepted" % d3,
                   ok is False, "detect(3,0.2)=%.6f" % d3))
    checks.append(("sensitivity: halving prevalence lowers detection at fixed n (fires the escalation)",
                   pinst.detect(n, 0.1) < pinst.detect(n, 0.2) < 1.0,
                   "detect(14,0.1)=%.4f < detect(14,0.2)=%.4f" % (pinst.detect(n, 0.1), pinst.detect(n, 0.2))))
    ms = doc.get("makespan") or {}
    lb = (ms.get("lower_bound_this_recompute_10x") or {})
    row0 = (lb.get("rows") or [{}])[0]
    want_be = float(row0.get("implementer_h", 0)) * 3600.0 / float(lb.get("census_slots", 1))
    checks.append(("break-even recompute: implementer_h*3600/census_slots == recorded t_review",
                   abs(float(row0.get("break_even_t_review_s", -1)) - want_be) <= 0.1,
                   "recorded=%s recomputed=%.4f" % (row0.get("break_even_t_review_s"), want_be)))
    checks.append(("prevalence recorded at 0.20 (a 20%%-defective class must be detected, not assumed rare)",
                   abs(p - 0.20) < 1e-12, "p=%s" % p))

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
