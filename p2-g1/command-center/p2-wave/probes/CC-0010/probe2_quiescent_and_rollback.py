#!/usr/bin/env python3
"""CC-0010 probe2 - mechanically different independent recheck (live, fail-closed).

Re-derives the quiescence proof through the recreated lib.py (two mechanically independent signals ANDed -- one signal is not proof) and re-checks every freeze class status.
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
OUT = REPO / "command-center/receipts/CC-0010.json"
UNIT = "CC-0010"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/receipts/CC-0010.json"
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
    spec = importlib.util.spec_from_file_location("cc0010_lib", HERE / "lib.py")
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    fp = doc.get("freeze_protocol") or {}
    lf = doc.get("live_freeze") or {}
    nine = [str(c) for c in (fp.get("nine_classes") or [])]
    checks.append(("lib.normalize: class id set equals the nine canonical freeze classes",
                   lib.normalize(nine) == lib.normalize(list(lib.NINE_CLASSES)),
                   "recorded=%d canonical=%d" % (len(nine), len(lib.NINE_CLASSES))))
    checks.append(("lib.all_captured: every class captured in live_freeze.class_status",
                   lib.all_captured(lf.get("class_status") or {}), ""))
    qs = (doc.get("controls") or {}).get("quiescent_scratch") or {}
    okq, n = lib.quiescence_signals(qs)
    checks.append(("quiescence re-derived: two INDEPENDENT signals (git digest + mtime scan) both hold",
                   okq and n == 2 and int(qs.get("independent_signal_count", -1)) == 2,
                   "ok=%s signals=%d" % (okq, n)))
    classes = lf.get("classes") or []
    checks.append(("per-class rows all carry captured status within the nine ids",
                   len(classes) >= 9 and all(str(r.get("id")) in nine and r.get("status") == "captured" for r in classes[:9]),
                   "rows=%d" % len(classes)))
    aw = (doc.get("controls") or {}).get("adversarial_writer") or {}
    checks.append(("adversarial writer refusal: live capture marked SAMPLE, never BASELINE",
                   aw.get("refused_baseline") is True and aw.get("verdict") == "SAMPLE", str(aw.get("verdict"))))

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
