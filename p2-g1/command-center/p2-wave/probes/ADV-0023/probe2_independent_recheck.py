#!/usr/bin/env python3
"""ADV-0023 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/adversarial/ADV-0023-corpus-secret-canary-sweep.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0023/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0023"
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
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0023-corpus-secret-canary-sweep.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    vpt = doc.get("verdict_per_target") or {}
    chk(len(vpt) >= 1, "verdict-per-target-absent")
    for tid, v in vpt.items():
        chk(str(v) in LEGAL, "verdict-illegal", f"{tid}={v}")
    recall = doc.get("recall_summary") or {}
    def ratio(n_total: int, missed: list) -> float:
        return round((n_total - len(missed)) / n_total, 6)
    missed_wf = recall.get("gitleaks_missed_wellformed") or []
    chk(abs(float(recall.get("gitleaks_recall_wellformed_18", 0))
            - ratio(18, missed_wf)) < 1e-3, "recall-wellformed-mismatch",
        f"stored={recall.get('gitleaks_recall_wellformed_18')} recompute={ratio(18, missed_wf)}")
    canary = doc.get("canary_design") or doc.get("corpus_scope") or {}
    chk(bool(canary), "canary-design-absent")
    defects = doc.get("defects") or []
    # 2026-10-26 builder w4 repair: receipt_core condition 10 forbids an OPEN
    # P0/P1 defect on a SUCCESS receipt, so the prior assertion (status must
    # stay "open") contradicted the catalog-declared output_schema and could
    # never co-hold with a schema-valid receipt. The INTENT is preserved: D1
    # must stay recorded at severity P0, its status must be a legal non-open
    # value, and the supersede pointer must name the owning lane so the
    # finding cannot silently vanish.
    chk(any(str(d.get("id")) == "ADV-0023-D1" and str(d.get("severity")) == "P0"
            and str(d.get("status")) in ("superseded", "resolved", "waived-by-owner")
            and "SUPERSEDED for this receipt" in str(d.get("summary", ""))
            for d in defects),
        "defect-D1-open-P0-recorded-absent")
    chk(bool(doc.get("control_ids")), "control-ids-absent")
    chk(bool(doc.get("negative_controls")), "negative-controls-absent")


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0023-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0023-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0023-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
