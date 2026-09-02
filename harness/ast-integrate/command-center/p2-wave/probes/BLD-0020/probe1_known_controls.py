#!/usr/bin/env python3
"""Probe 1: four known M-NN namespaces, dangling ZX, planted QQ collision."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ROOTS = [HERE / "fixtures" / "estate", HERE / "fixtures" / "controls"]


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0020-probe1 {msg}")
    return 1


def main() -> int:
    snap = C.walk(ROOTS)
    known, method = C.known_namespaces(snap, ROOTS)
    missing = [r["id"] for r in known if not r["found"]]
    if missing:
        return fail(f"known-namespaces-missing:{missing} method={method}")
    if len(known) != 4:
        return fail(f"known-count:{len(known)}")
    decls = C.declarations_by_prefix(snap)
    dang = {row["prefix"] for row in C.dangling(snap)}
    if "ZX" not in dang:
        return fail(f"ZX-not-dangling dangling={sorted(dang)}")
    if "ZX" in decls:
        return fail("ZX-classified-as-namespace")
    qq = decls.get("QQ", set())
    if len(qq) != 2:
        return fail(f"planted-QQ-registry-count:{sorted(qq)}")
    m_regs = decls.get("M", set())
    if len(m_regs) < 3:
        return fail(f"M-declaring-registries:{sorted(m_regs)}")
    payload = {
        "probe": "probe1-known-controls",
        "known_found": [r["id"] for r in known],
        "detection_method": method,
        "M_registries": sorted(m_regs),
        "QQ_registries": sorted(qq),
        "ZX_dangling": True,
        "files_scanned": snap.files_scanned,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "known=4 ZX=DANGLING QQ="
        f"{len(qq)}-registries M={len(m_regs)}-registries method={method}"
    )
    print("SUCCESS:BLD-0020-probe1 four-known dangling-ZX planted-QQ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
