#!/usr/bin/env python3
"""Shard-7 wave-5 receipt completions (IMP-0006, IMP-0044, IMP-0031).

IMP-0006: add required receipt_core field `spec_anchor`
          (anchor cited by the unit's own target text: spec:10483).
IMP-0044: add required receipt_core fields `timestamps` + `retry`
          (timestamps derived from on-disk probe/receipt mtimes; retry matches
          the catalog retry_policy and the observable zero-retry build).
IMP-0031: move schema-invalid `rerun_at` out of `timestamps`
          (additionalProperties:false) into `extensions` (sanctioned channel).

Each edit recomputes the CRLF-normalized sha256 and refreshes the unit's row
in probes/<id>/UNIT-ARTIFACT-MANIFEST.json so _measure_one_delivered.py stays
green. Run with: python -B _builder_shard7_w5_fixups.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent


def detect_indent(text: str) -> int:
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return 2


def norm_sha(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def edit_imp0006(d: dict) -> None:
    d["spec_anchor"] = "_USER-PROMPTS.md:10483"


def edit_imp0044(d: dict) -> None:
    d["timestamps"] = {
        "started_at": "2026-10-24T23:22:57Z",
        "ended_at": "2026-10-24T23:23:29Z",
    }
    d["retry"] = {"count": 0, "policy": "two-strikes-then-pivot"}


def edit_imp0031(d: dict) -> None:
    ts = d.get("timestamps") or {}
    rerun = ts.pop("rerun_at", None)
    d["timestamps"] = ts
    if rerun is not None:
        d.setdefault("extensions", {})["rerun_at"] = rerun


EDITS = {
    "IMP-0006": edit_imp0006,
    "IMP-0044": edit_imp0044,
    "IMP-0031": edit_imp0031,
}


def main() -> int:
    for uid, fn in EDITS.items():
        rp = REPO / f"command-center/receipts/{uid}.json"
        raw = rp.read_bytes()
        ascii_only = all(b < 128 for b in raw)
        text = raw.decode("utf-8")
        d = json.loads(text)
        before_keys = set(d.keys())
        fn(d)
        new_text = (
            json.dumps(
                d,
                indent=detect_indent(text),
                ensure_ascii=ascii_only,
            )
            + "\n"
        )
        rp.write_bytes(new_text.encode("utf-8"))
        new_sha = norm_sha(rp)

        mp = REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        mraw = mp.read_bytes()
        m_ascii = all(b < 128 for b in mraw)
        mtext = mraw.decode("utf-8")
        m = json.loads(mtext)
        hit = False
        for row in m.get("artifacts") or []:
            row_path = str(row.get("path", "")).replace("\\", "/")
            if row.get("unit_id") == uid and row_path == rp.as_posix():
                row["sha256"] = new_sha
                row["present"] = True
                hit = True
        if not hit:
            print(f"FAILED:{uid} no matching manifest row")
            return 1
        mp.write_bytes(
            (json.dumps(m, indent=detect_indent(mtext), ensure_ascii=m_ascii) + "\n").encode("utf-8")
        )
        added = sorted(set(d.keys()) - before_keys)
        print(f"SUCCESS:{uid} receipt updated; added={added}; manifest sha -> {new_sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
