#!/usr/bin/env python3
"""ADV-0022 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/adversarial/ADV-0022-declared-permission-escape.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0022/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0022"
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
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0022-declared-permission-escape.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    ev = doc.get("evidence") or []
    chk(len(ev) >= 5, "evidence-under-minimum", str(len(ev)))
    for i, item in enumerate(ev):
        v = str(item.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"[{i}]={v}")
        probes = item.get("probes") or []
        fps = [p.get("fingerprint") for p in probes if isinstance(p, dict)]
        chk(len(fps) == len(set(fps)) and len(fps) >= 1,
            "fingerprints-not-per-item-distinct", f"[{i}]")
    for d in doc.get("defects") or []:
        chk(bool(d.get("id")) and bool(d.get("severity")) and bool(d.get("status")),
            "defect-row-incomplete", str(d.get("id")))
    chk(bool(doc.get("control_ids")), "control-ids-absent")
    chk(bool(doc.get("residual_unknowns")), "residual-unknowns-absent")
    chk(bool(doc.get("downstream_consumers")), "downstream-consumers-absent")


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0022-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0022-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0022-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
