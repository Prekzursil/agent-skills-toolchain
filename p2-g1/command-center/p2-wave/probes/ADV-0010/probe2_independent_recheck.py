#!/usr/bin/env python3
"""ADV-0010 probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's claims from its own raw rows and live inputs
(counts, census, internal consistency, live referenced files) and
byte-compares the per-unit manifest registration against the live artifact
(LF-normalized sha256, matching _measure_one_delivered.py). Fails closed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0010/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0010"
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def manifest_byte_compare(doc: dict) -> None:
    chk(MANIFEST.is_file(), "manifest-absent")
    if not MANIFEST.is_file():
        return
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = lf_sha(OUT)
    rows = [a for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == UNIT]
    chk(bool(rows), "manifest-row-absent")
    match = [a for a in rows
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    mutations = doc.get("mutations") or []
    k = int(doc.get("killed_count") or 0)
    s = int(doc.get("survived_count") or 0)
    chk(k + s == len(mutations), "killed+survived!=mutations",
        f"{k}+{s}!={len(mutations)}")
    recomputed_k = sum(1 for m in mutations if str(m.get("status")) == "KILLED")
    recomputed_s = len(mutations) - recomputed_k
    chk(recomputed_k == k and recomputed_s == s, "mutation-census-mismatch",
        f"rows: KILLED={recomputed_k} other={recomputed_s} vs {k}/{s}")
    survivors = [m for m in mutations if str(m.get("status")) != "KILLED"]
    for m in survivors:
        # fail_open may be a true fail-open proof (true) or a strictness flip
        # that survives trivially (false) - the field must be RECORDED either
        # way, and every survivor must carry its suite evidence row
        chk(m.get("fail_open") is not None, "survivor-fail-open-unrecorded",
            str(m.get("id")))
        chk(bool(m.get("failed_tests")) or bool(m.get("suite")),
            "survivor-evidence-absent", str(m.get("id")))
    controls = doc.get("controls") or []
    names = {str(c.get("id") or c) for c in controls} if isinstance(controls, list) else set(controls)
    for need in ("unmutated_baseline_green", "killed_mutation_proves_suite_ran",
                 "both_named_probes_recorded"):
        chk(any(need in n for n in names), "control-absent", need)
    gate = str(doc.get("gate_under_test") or "")
    chk(bool(gate), "gate-under-test-absent")


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0010-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0010-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0010-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
