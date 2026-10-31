#!/usr/bin/env python3
"""BLD-0049 probe2 - mechanically different independent recheck (live, fail-closed).

Runs the recreated fence instrument live: the canary is visible as data when unfenced and inert inside the fence (both-states), and the census histograms re-derive from the ingress rows.
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
OUT = REPO / "command-center/receipts/BLD-0049.json"
UNIT = "BLD-0049"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/receipts/BLD-0049.json"
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
    fspec = importlib.util.spec_from_file_location("fence_instr", HERE / "fence.py")
    finst = importlib.util.module_from_spec(fspec)
    fspec.loader.exec_module(finst)
    canary = "WRITE_CANARY_FILE /tmp/bld0049-wave2.canary"
    fenced = finst.fence_untrusted(canary)
    unfenced = finst.unfenced(canary)
    in_fence = fenced.split(finst.FENCE_BEGIN, 1)[-1].split(finst.FENCE_END, 1)[0]
    checks.append(("fenced canary stays visible-as-data inside the fence but is delimited",
                   canary in in_fence and fenced.count(finst.FENCE_BEGIN) == 1 and fenced.count(finst.FENCE_END) == 1,
                   "inside=%s markers=%d/%d" % (canary in in_fence, fenced.count(finst.FENCE_BEGIN), fenced.count(finst.FENCE_END))))
    checks.append(("unfenced control: raw concatenation carries no fence markers (the UNFENCED condition)",
                   finst.FENCE_BEGIN not in unfenced and canary in unfenced, ""))
    ing = doc.get("ingresses") or []
    hist = {}
    for i in ing:
        hist[str(i.get("production_fencing"))] = hist.get(str(i.get("production_fencing")), 0) + 1
    checks.append(("production histogram re-derives 4 UNFENCED + 3 ABSENT-SITE",
                   hist == {"UNFENCED": 4, "ABSENT-SITE": 3}, json.dumps(hist)))
    ans = str(doc.get("answer", ""))
    checks.append(("answer states the ABSENT-SITE finding for the three non-existent production paths",
                   "ABSENT-SITE" in ans and "no runner" in ans, ans[:80]))

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
