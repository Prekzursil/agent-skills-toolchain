#!/usr/bin/env python3
"""Probe 2: independent reviewer — manifest sha + evidence probes for ADV-0070."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
sys.path.insert(0, str(REPO))
import p2_jsonschema_hook  # noqa: E402

UID = "ADV-0070"
REL = "command-center/adversarial/ADV-0070-web-content-injection-into-research.json"
SENT = "SUCCESS:ADV-0070 emitted ONLY when the artifact at output_path exists, is non-empty, parses against output_schema, records BOTH named probes verbatim with their raw output, carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and records the result of every listed control/negative test. Any missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0070 <reason>."


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    art = REPO / REL
    if not art.is_file():
        return fail("artifact-absent")
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENT and SENT not in text:
        return fail("sentinel-absent")
    live = digest(art)
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        return fail("manifest-absent")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == UID
    ]
    if not rows:
        return fail("manifest-row-absent")
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == REL
        and str(a.get("sha256") or "") == live
        and a.get("present") is True
    ]
    if not matching:
        return fail(f"manifest-sha-mismatch live={live}")
    if isinstance(doc, dict):
        ev = doc.get("evidence") if isinstance(doc.get("evidence"), list) else []
        n_probe_roles = 0
        for item in ev:
            if not isinstance(item, dict):
                continue
            probes = item.get("probes") if isinstance(item.get("probes"), list) else []
            n_probe_roles += sum(1 for p in probes if isinstance(p, dict))
        named = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
        if n_probe_roles < 2 and len(named) < 2:
            # schema-class artifacts have no evidence envelope; still require parse
            if "$schema" not in doc and "unit_id" in doc:
                return fail("named-probes-thin")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
    print(f"manifest_sha_ok=True live={live} rows={len(rows)}")
    print(f"SUCCESS:{UID}-probe2 independent manifest+envelope reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
