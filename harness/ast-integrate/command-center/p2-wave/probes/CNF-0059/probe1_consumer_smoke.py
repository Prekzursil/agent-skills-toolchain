#!/usr/bin/env python3
"""Probe 1: re-run every consumer smoke and require printed resolved library paths."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import downstream as D  # noqa: E402

REPO = D.REPO
ART = REPO / "command-center/confirmation/CNF-0059-downstream-consumers.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0059-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0059":
        print("FAILED:CNF-0059-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0059-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0059" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0059-probe1 sentinel absent")
        return 1

    answer, _art_consumers = D.artifact_payload(doc)
    live = D.measure()
    changed = Path(live["lib_changed_path"]).resolve()
    smoked = 0
    for row in live["consumers"]:
        cid = row["id"]
        finding = row["finding"]
        if finding == "unprotected":
            print(f"consumer id={cid} finding=unprotected reason={row.get('unprotected_reason')}")
            continue
        code = row.get("exit_code")
        resolved = row.get("resolved_library_path")
        print(f"RESOLVED_LIB id={cid} exit={code} finding={finding} path={resolved}")
        if code is None or not resolved:
            print(f"FAILED:CNF-0059-probe1 {cid} missing exit or resolved path")
            return 1
        smoked += 1
        try:
            real = str(Path(resolved).resolve())
        except OSError:
            print(f"FAILED:CNF-0059-probe1 {cid} resolved path not real {resolved}")
            return 1
        if str(changed) not in real:
            print(f"FAILED:CNF-0059-probe1 {cid} did not exercise changed copy")
            print(f"  changed={changed}")
            print(f"  resolved={real}")
            return 1

    if smoked < 3:
        print(f"FAILED:CNF-0059-probe1 smoked={smoked} want>=3")
        return 1
    if "cnf0059-smoke-pass" not in live["ok_ids"]:
        print("FAILED:CNF-0059-probe1 passing fixture did not pass")
        return 1
    if "cnf0059-smoke-break" not in live["broken_ids"]:
        print("FAILED:CNF-0059-probe1 breaking fixture did not break")
        return 1
    if "cnf0059-pin-stale" not in live["pin_invalidated_ids"]:
        print("FAILED:CNF-0059-probe1 stale pin not detected")
        return 1
    art_broken = set(answer.get("which_consumers_break") or [])
    if art_broken != set(live["broken_ids"]):
        print(f"FAILED:CNF-0059-probe1 artifact broken != live {art_broken} {live['broken_ids']}")
        return 1
    print(f"smoked={smoked} broken={live['broken_ids']} pins={live['pin_invalidated_ids']}")
    print("SUCCESS:CNF-0059-probe1 consumer smokes printed resolved changed-lib paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
