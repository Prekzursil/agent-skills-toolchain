#!/usr/bin/env python
"""PreToolUse hook — compchem pre-flight probe (simplest-probe-first for expensive MD/docking).

Fires before an EXPENSIVE Schrodinger MCP op (glide_dock / prime_mmgbsa) and, once per session,
injects a reminder to run a CHEAP sanity probe FIRST (molecule_properties / qikprop_admet / RDKit
descriptors — verify MW / formula / net charge / stereo match the INTENDED structure) so a bad
ligand prep doesn't burn GPU/compute hours. This operationalizes the F1 simplest-probe-first skill
for the user's active compchem domain — motivated by a real incident (a 1-carbon SMILES slip:
beta-phenyl-beta-alanine MW 165 docked instead of phenibut MW 179, caught only by a manual MW check).

Hook LAW: TRIGGER + inject an external reminder; the agent JUDGES. NEVER blocks. Fail-open (exit 0).
Once per session (sentinel file) so it reminds, never nags repeated docks.

Opt-out:  COMPCHEM_PREFLIGHT=off  in env, or  hooks/compchem-preflight/.disabled
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get(
        "COMPCHEM_PREFLIGHT_ROOT", str(Path.home() / ".claude" / "compchem-preflight")
    )
)
THIS = Path(__file__).resolve().parent


def _already_reminded(session_id: str) -> bool:
    """True if we already reminded this session (and mark it). Fail-open -> False (re-remind, harmless)."""
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        safe = (
            "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
                :80
            ]
            or "unknown"
        )
        flag = ROOT / f"{safe}.flag"
        if flag.exists():
            return True
        flag.write_text("1", encoding="utf-8")
        return False
    except Exception:
        return False


def main() -> int:
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "COMPCHEM_PREFLIGHT", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        tool = str(data.get("tool_name") or "")
        if not ("glide_dock" in tool or "prime_mmgbsa" in tool):
            return 0
        if _already_reminded(str(data.get("session_id") or "unknown")):
            return 0
        msg = (
            "**[compchem pre-flight - simplest-probe-first]** About to run an EXPENSIVE op "
            f"(`{tool}`). Before committing GPU/compute, confirm the CHEAP probes passed:\n"
            "1. Ligand IDENTITY is correct - run `mcp__schrodinger__molecule_properties` (or RDKit / "
            "`qikprop_admet`) and check the **MW / formula / net charge match the INTENDED structure**, "
            "not just the name. A one-atom SMILES slip is a different molecule (e.g. 165 vs 179 Da).\n"
            "2. Protonation/stereo are right (zwitterion at the assay pH; correct enantiomer/geometry).\n"
            "3. For docking: the grid/receptor passed its redock-RMSD validation gate.\n"
            "Garbage-in wastes GPU-hours. (This reminder fires once per session.)"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": msg,
                    }
                }
            )
        )
    except Exception:
        pass  # fail-open: never crash a tool call
    return 0


if __name__ == "__main__":
    sys.exit(main())
