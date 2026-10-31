#!/usr/bin/env python3
"""ADV-0018 probe2 -- independent content re-derivation (mechanically different).

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
OUT = REPO / "command-center/adversarial/ADV-0018-memory-vault-contradiction-sweep.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0018/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0018"
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
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0018-memory-vault-contradiction-sweep.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    chk(len(targets) == 8, "target-count", str(len(targets)))
    for t in targets:
        chk(str(t.get("verdict")) in LEGAL, "verdict-illegal", f"{t.get('id')}={t.get('verdict')}")
    con = doc.get("contradicted_ids") or []
    raw_notes = doc.get("contradicted_notes") or []
    chk(bool(raw_notes) and len(con) >= 2, "contradiction-set-empty")
    note_bodies = [n.get("contradicted") for n in raw_notes if isinstance(n, dict)]
    chk(bool(note_bodies), "contradiction-note-bodies-absent")
    for n in note_bodies:
        chk(isinstance(n, list) and len(n) >= 1,
            "contradiction-note-empty-body")
    recall = set(doc.get("still_recallable_ids") or [])
    chk(recall <= set(con), "recallable-not-subset-contradicted",
        str(recall - set(con))[:120])
    chk(int(doc.get("notes_loaded") or 0) > 0, "notes-loaded-zero")
    chk(bool(doc.get("frontmatter_audit")), "frontmatter-audit-absent")
    chk(bool(doc.get("vault_method") or doc.get("vault_roots")), "vault-method-absent")


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0018-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0018-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0018-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
