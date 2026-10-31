#!/usr/bin/env python3
"""ADV-0090 probe2 -- mechanically different independent recheck (live, fail-closed).

Lane 1: byte-compare the per-unit manifest sha (LF-normalized) against the
live artifact. Lane 2: re-derive the unit's headline claims from artifact
internals. Lane 3: mutation negative control - the structural predicate must
FIRE on a tampered copy and stay SILENT on the real artifact. Writes nc_live.json.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json"
UNIT = "ADV-0090"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
VOCAB = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def digest_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def structural_fires(text: str) -> tuple[bool, str]:
    """The minimal predicate probe1 embodies; used for the mutation control."""
    try:
        doc = json.loads(text)
    except Exception:
        return True, "parse-error"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("unit_id") != UNIT:
        return True, "unit-id-mismatch"
    tgt = (
        doc.get("targets")
        or doc.get("verdicts")
        or doc.get("enumerated_targets")
        or doc.get("component_matrix")
    )
    if not tgt:
        if not doc.get("overall_verdict"):
            return True, "targets-collapsed"
    else:
        vocab = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
        vs = [t.get("verdict") for t in tgt if isinstance(t, dict) and t.get("verdict") is not None]
        if not vs or any(v not in vocab for v in vs):
            return True, "verdict-vocabulary"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json"
            and str(a.get("sha256", "")) == live
            and a.get("present") is True
        ]
        checks.append((
            "manifest sha row matches live artifact (LF-normalized)",
            bool(match),
            f"sha={live[:16]}... rows={len(rows)}",
        ))
        if not match:
            fails.append("manifest-sha-mismatch")

    # Lane 2: unit-specific re-derivation
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unparseable: {type(exc).__name__}")
        return 1

    nc = next((c for c in doc.get("negative_controls") or [] if c.get("id") == "synthetic-6-of-10-flaky-fixture"), None)
    bad = str((nc or {}).get("bad_state_output", ""))
    good = str((nc or {}).get("good_state_output", ""))
    checks.append((
        "flaky fixture both-states: bad fires flaky 6/10, good silent 10/10",
        bool(nc) and "passes=6/10" in bad and "flaky_by_contract=True" in bad
        and "passes=10/10" in good and "flaky_by_contract=False" in good
        and nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
        f"bad[:60]={bad[:60]!r} good[:60]={good[:60]!r}",
    ))
    rep = doc.get("report") or {}
    checks.append((
        "report.overall_verdict == top-level overall_verdict (PARTIAL, no green-laundering)",
        rep.get("overall_verdict") == doc.get("overall_verdict") == "PARTIAL",
        f"report={rep.get('overall_verdict')} top={doc.get('overall_verdict')}",
    ))
    checks.append((
        "probe1_answer == report.answer (single source of truth, no drift)",
        doc.get("probe1_answer") == rep.get("answer") and bool(doc.get("probe1_answer")),
        f"len={len(str(doc.get('probe1_answer', '')))}",
    ))
    det = [t for t in doc.get("tests") or [] if "deterministic-control-10-of-10" in str(t.get("id", ""))]
    checks.append((
        "deterministic control recorded PASS 10/10",
        len(det) >= 1 and det[0].get("result") == "PASS",
        f"rows={len(det)} result={det[0].get('result') if det else None}",
    ))

    for label, ok, detail in checks:
        if not ok:
            fails.append(f"{label} ({detail})")

    # Lane 3: mutation negative control (both-states)
    real_doc = json.loads(OUT.read_text(encoding="utf-8"))
    real_doc["unit_id"] = "XXXX-0000"
    tamper = json.dumps(real_doc, ensure_ascii=False, indent=1)
    fired_t, why_t = structural_fires(tamper)
    fired_r, why_r = structural_fires(OUT.read_text(encoding="utf-8"))
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICTOR-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1), encoding="utf-8", newline="\n")
    if not control_ok:
        fails.append(f"mutation control: tampered-fired={fired_t} real-fired={fired_r} ({why_t}/{why_r})")

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
        print(f"FAILED:{UNIT}-probe2 {'; '.join(fails)}")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 manifest sha match, {len(checks)} rederivations hold, mutation control both-states ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
