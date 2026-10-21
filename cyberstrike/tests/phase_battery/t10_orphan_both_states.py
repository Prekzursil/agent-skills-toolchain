#!/usr/bin/env python3
"""T-10 orphan both-states - the CS-2 defect must be PRESENT pre-patch and
ABSENT post-patch. A gate that can only ever say green is not a gate.

State A (measurable NOW): the UNPATCHED installed binary v1.1.16 reconciles
nothing at startup (vehicle verdict), so a bounded census over recent
sessions is expected to find stuck non-terminal parts (>0) - the positive
control that the defect class is still observable. A zero here is recorded
honestly (sessions may have aged out of the --limit window), not forced.

State B (PENDING-OWNER): the G-10 callID patch (phase2-5/callid_patch.diff,
built against src-v1.1.16; receipt stage5_g10_callid_receipt.json) is NOT
deployed - installation is owner-gated. After deployment, re-run this test:
census must drive to ZERO stuck parts for the gate to close.

This mirrors T-9's substrate (orphan_census.py) but is the BOTH-STATES gate;
T-9 is the per-run measurement. Two-signal guard per the census docstring:
a stuck count corroborated only by one query pass is flagged
needs_corroboration and never acted on alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    SCRIPTS,
    SUCCESS,
    FAILED,
    PENDING_OWNER,
    VerdictRecorder,
    py_run,
    json_from_completed,
)

CENSUS = SCRIPTS / "orphan_census.py"
PATCH = Path(
    r"D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase2-5"
    r"\callid_patch.diff"
)
PATCH_RECEIPT = Path(
    r"D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase2-5"
    r"\stage5_g10_callid_receipt.json"
)


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    opts = opts or {}
    limit = opts.get("limit", 50)
    if not CENSUS.is_file():
        rec.record("T-10", FAILED, reason="orphan_census.py missing", anchors=[CENSUS])
        return FAILED

    ctrl = py_run(CENSUS, ["--self-test"])
    if ctrl.returncode != 0:
        rec.record(
            "T-10", FAILED, reason="census self-test control failed", anchors=[CENSUS]
        )
        return FAILED

    out = rec.out_dir / "t10_census.json"
    r = py_run(CENSUS, ["--json", str(out), "--limit", str(limit)], timeout=600)
    data = json_from_completed(r)
    if not data and out.exists():
        import json

        data = json.loads(out.read_text(encoding="utf-8", errors="replace"))
    if r.returncode not in (0, 2) or not data:
        rec.record(
            "T-10", FAILED, reason=f"census error (rc={r.returncode})", anchors=[CENSUS]
        )
        return FAILED

    total = data.get("stuck_calls_total")
    scanned = data.get("scanned")
    orphan_sessions = data.get("orphan_sessions")
    state_a_present = bool(total) and total > 0

    rec.hit(
        "T-10",
        "state_A_unpatched",
        rc=r.returncode,
        stuck_calls_total=total,
        sessions_scanned=scanned,
        orphan_sessions=orphan_sessions,
        defect_observable=state_a_present,
    )

    patch_built = PATCH.is_file() and PATCH_RECEIPT.is_file()
    rec.record(
        "T-10",
        PENDING_OWNER,
        reason="state B awaits G-10 callID patch deployment (owner-gated)",
        details={
            "state_A": {
                "binary": "installed v1.1.16 (unpatched)",
                "stuck_calls_total": total,
                "orphan_sessions": orphan_sessions,
                "sessions_scanned": scanned,
                "defect_observable": state_a_present,
                "note": "zero is recorded honestly (window may have "
                "aged out), never forced green",
            },
            "state_B": {
                "patch": str(PATCH),
                "built": patch_built,
                "deployed": False,
                "closes_when": "post-deploy census shows 0 stuck "
                "parts (re-run this test)",
            },
        },
        anchors=[CENSUS] + ([PATCH] if patch_built else []),
    )
    return PENDING_OWNER


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-10"}) as rec:
        status = run(rec, {"limit": args.limit})
        print(f"T-10 {status}")
        return 0 if status in (SUCCESS, PENDING_OWNER) else 1


if __name__ == "__main__":
    sys.exit(main())
