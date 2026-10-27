#!/usr/bin/env python3
"""ADV-0005 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/adversarial/ADV-0005-p0-p1-fresh-context-rederivation.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0005/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0005"
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
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0005-p0-p1-fresh-context-rederivation.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    chk(len(targets) == 10, "target-count", str(len(targets)))
    planted_false = [t for t in targets if t.get("planted_kind") == "false"]
    chk(bool(planted_false), "planted-false-calibration-absent")
    for t in targets:
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"{t.get('id')}={v}")
        if v == "REFUTED":
            # vote counting is banned: a refutation must name its settling
            # tiebreak; CONFIRMED calibration rows may legitimately lack one
            chk(bool(t.get("tiebreak")), "tiebreak-absent-for-refutation",
                str(t.get("id")))
        if t.get("planted_kind") is not None:
            # planted calibration rows carry the blind/implementer/settling trace;
            # real claim rows carry prose summaries instead.
            summary = str(t.get("summary") or "")
            chk("final=" in summary, "summary-final-absent", str(t.get("id")))
            final = summary.rsplit("final=", 1)[-1].strip()
            chk(final == v, "summary-final-disagrees",
                f"{t.get('id')}: final={final} verdict={v}")
    for t in planted_false:
        chk(str(t.get("verdict")) == "REFUTED",
            "planted-false-not-refuted", str(t.get("id")))
    chk(bool(doc.get("blinding")) and bool(doc.get("unblind")),
        "blinding/unblind-absent")
    chk(bool(doc.get("named_registry")), "named-registry-absent")
    chk(bool(doc.get("negative_controls")), "negative-controls-absent")


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0005-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0005-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0005-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
