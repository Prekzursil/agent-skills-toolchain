#!/usr/bin/env python3
"""Probe 1: reproduce the escape-hatch case against the A2 design artifact.

Both-states: typed registry refuses opaque_body; hatch capture-back makes a
hand-edit CLEAN. Blast radius is counted from generate(), not asserted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import payload as P  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/REFUTATION.json"
DESIGN = REPO / "command-center/phase3/A2/DESIGN.json"


def main() -> int:
    run = S.run_scenario()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:ARC-0016-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0016-probe1 REFUTATION.json missing")
        return 1
    if not DESIGN.is_file():
        print("FAILED:ARC-0016-probe1 DESIGN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = P.domain(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0016-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (body.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("typed_rejects_hatch") is True
        and rec.get("hatch_reintroduces_drift") is True
        and rec.get("blast_radius_equals_file_count") is True
    )
    if not rec_ok:
        print("FAILED:ARC-0016-probe1 REFUTATION reproduction flags false")
        return 1
    proc = (body.get("scenario") or {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0016-probe1 procedure too short")
        return 1
    silent = str((body.get("scenario") or {}).get("silent_loss_file") or "")
    if not silent.startswith("command-center/phase3/A2/DESIGN.json:"):
        print(f"FAILED:ARC-0016-probe1 silent_loss_file not DESIGN.json: {silent}")
        return 1
    try:
        line = int(silent.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        print(f"FAILED:ARC-0016-probe1 silent_loss_file not file:line {silent}")
        return 1
    dlines = DESIGN.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(dlines):
        print("FAILED:ARC-0016-probe1 DESIGN line oob")
        return 1
    if "escape-hatch" not in dlines[line - 1] and "opaque" not in dlines[line - 1]:
        print("FAILED:ARC-0016-probe1 DESIGN line does not name the hatch class")
        return 1
    art_br = body.get("blast_radius") or {}
    live_n = int(run["generated_file_count"])
    live_a = int(run["files_affected_by_one_shared_path_bug"])
    if int(art_br.get("generated_file_count") or 0) != live_n:
        print("FAILED:ARC-0016-probe1 artifact blast count != live generate()")
        return 1
    if int(art_br.get("files_affected_by_one_shared_path_bug") or 0) != live_a:
        print("FAILED:ARC-0016-probe1 artifact affected count != live")
        return 1
    if live_n != live_a:
        print("FAILED:ARC-0016-probe1 blast radius != generated file count")
        return 1
    if "SUCCESS:ARC-0016" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0016-probe1 sentinel absent")
        return 1
    print(
        "typed_rejects="
        f"{bool(run.get('typed_rejects_hatch'))} "
        f"hatch_drift={bool(run.get('hatch_reintroduces_drift'))} "
        f"blast={live_a}/{live_n}"
    )
    print("SUCCESS:ARC-0016-probe1 escape-hatch scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
