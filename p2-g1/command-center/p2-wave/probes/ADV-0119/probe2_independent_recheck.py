#!/usr/bin/env python3
"""ADV-0119 probe2 -- mechanically different independent recheck (live, fail-closed).

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
OUT = REPO / "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json"
UNIT = "ADV-0119"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json"
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

    tp = doc.get("three_point_inventory") or {}
    empties = all(
        (tp.get(k) == []) for k in ("missing_files", "altered_files", "missing_commands", "leftover_commands")
    )
    checks.append((
        "three-point inventory: byte-identical user data, commands restored, zero N-only residue",
        tp.get("user_byte_identical") is True and tp.get("commands_restored") is True
        and tp.get("no_n_only_leftover") is True and empties,
        f"user_byte_identical={tp.get('user_byte_identical')} commands={tp.get('commands_restored')} "
        f"residue={tp.get('no_n_only_leftover')} empty_lists={empties}",
    ))
    gj = doc.get("golden_journeys") or {}
    pre_rows = ((gj.get("pre_upgrade") or {}).get("rows")) or []
    checks.append((
        "golden journeys pass after rollback; pre-upgrade rows all rc=0",
        gj.get("post_rollback_pass") is True and pre_rows and all(r.get("rc") == 0 and r.get("ok") is True for r in pre_rows),
        f"post={gj.get('post_rollback_pass')} pre_rows={len(pre_rows)}",
    ))
    tg = doc.get("enumerated_targets") or []
    checks.append((
        "all five enumerated targets CONFIRMED",
        len(tg) == 5 and all(t.get("verdict") == "CONFIRMED" for t in tg),
        f"targets={len(tg)} verdicts={[t.get('verdict') for t in tg]}",
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
