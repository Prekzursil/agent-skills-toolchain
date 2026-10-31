#!/usr/bin/env python3
"""Probe 1: planted template edit in a scratch clone is caught by the pin gate.

Also re-checks SECURITY.json recorded the demonstration (use, not mention)
and that clean generate() still matches the pin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/SECURITY.json"


def main() -> int:
    run = S.run()
    planted = run["planted_edit"]
    print(
        f"planted caught={planted['caught']} tripped={planted['tripped']} "
        f"reason={planted['reason']} changed={planted['files_changed']}/"
        f"{planted['file_count']}"
    )
    print(f"clean silent={run['clean']['silent']} files={run['file_count']}")
    print(
        f"pin_absent fail_closed={run['pin_absent']['fail_closed']} "
        f"reason={run['pin_absent']['reason']}"
    )
    print(f"provenance_ok={run['provenance']['ok']} n={run['provenance']['count']}")
    if not run.get("executed"):
        print("FAILED:ARC-0013-probe1 scenario executed=False")
        return 1
    if not planted.get("caught"):
        print("FAILED:ARC-0013-probe1 planted edit not caught")
        return 1
    if planted["files_changed"] != planted["file_count"]:
        print("FAILED:ARC-0013-probe1 planted edit did not change every output")
        return 1
    if not run["clean"]["silent"]:
        print("FAILED:ARC-0013-probe1 live generate tripped the pin")
        return 1
    if not run["pin_absent"]["fail_closed"]:
        print("FAILED:ARC-0013-probe1 missing pin did not fail closed")
        return 1
    if not run["provenance"]["ok"]:
        print("FAILED:ARC-0013-probe1 provenance missing")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0013-probe1 SECURITY.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0013" not in text:
        print("FAILED:ARC-0013-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0013-probe1 self-declared {doc.get('state')}")
        return 1
    demo = doc.get("demonstration") or {}
    rec = (demo.get("planted_edit") or {}).get("caught")
    if rec is not True:
        print("FAILED:ARC-0013-probe1 artifact did not record planted catch")
        return 1
    if (demo.get("pin_absent") or {}).get("fail_closed") is not True:
        print("FAILED:ARC-0013-probe1 artifact did not record fail-closed")
        return 1
    named = doc.get("named_template_files") or []
    if not any(
        isinstance(r, dict)
        and r.get("path") == "command-center/p2-wave/probes/ARC-0010/generator.py"
        for r in named
    ):
        print("FAILED:ARC-0013-probe1 generator.py not named as template")
        return 1
    print("SUCCESS:ARC-0013-probe1 planted-edit scratch-clone gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
