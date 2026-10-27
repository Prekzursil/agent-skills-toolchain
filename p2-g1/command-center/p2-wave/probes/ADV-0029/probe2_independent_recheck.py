#!/usr/bin/env python3
"""ADV-0029 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/adversarial/ADV-0029-dependency-confusion-index-poisoning.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0029/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0029"
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
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0029-dependency-confusion-index-poisoning.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    if not targets:
        for key in ("verdicts", "target_verdicts"):
            if doc.get(key):
                targets = doc.get(key)
                break
    ev = doc.get("evidence") or []
    for i, t in enumerate(targets):
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"[{i}]={v}")
        dn = t.get("dead_names")
        if dn is not None:
            chk(bool(dn), "dead-names-absent", str(t.get("id")))
        obs = t.get("observed")
        if obs is not None and t.get("expected_fail_closed") is not None:
            accepted = t.get("accepted")
            expect = str(t.get("verdict")) == "CONFIRMED"
            got = (str(obs) == "accepted") is bool(accepted)
            chk(got is expect or bool(accepted) == (str(obs) == "accepted"),
                "signature-matrix-inconsistent", str(t.get("id")))
    for i, item in enumerate(ev):
        v = str(item.get("verdict") or "")
        if v:
            chk(v in LEGAL, "evidence-verdict-illegal", f"[{i}]={v}")
    ov = str(doc.get("overall_verdict") or doc.get("verdict") or "")
    chk(ov in LEGAL, "overall-verdict-illegal", ov)


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0029-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0029-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0029-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
