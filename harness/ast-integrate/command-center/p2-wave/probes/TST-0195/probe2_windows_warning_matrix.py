#!/usr/bin/env python3
"""Probe 2: Windows leg + warning stream + silent-mutant detector + second shell."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import lookup as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0195-probe2 {msg}")
    return 1


def main() -> int:
    names = H.listing(H.ROOT)
    if "skills" not in names or "Skills" in names:
        return fail(f"independent listdir {names}")

    linux_mis = L.lookup(H.ROOT, H.MISMATCH, L.LINUX)
    win_mis = L.lookup(H.ROOT, H.MISMATCH, L.WINDOWS)
    win_exact = L.lookup(H.ROOT, H.EXACT, L.WINDOWS)
    silent = L.silent_windows_lookup(H.ROOT, H.MISMATCH)

    if linux_mis.ok:
        return fail("independent linux mismatch must miss")
    if not win_exact.ok or win_exact.warnings:
        return fail(f"windows exact must be silent {win_exact}")
    if not win_mis.ok:
        return fail(f"windows mismatch should warn-resolve, got miss {win_mis}")
    if not win_mis.warnings:
        return fail("windows mismatch hit with empty warning stream")
    if not win_mis.names_mismatch("Skills", "skills"):
        return fail(f"warning does not name both spellings {win_mis.warnings}")
    if win_mis.resolved != "skills":
        return fail(f"windows resolved {win_mis.resolved} want skills")

    ok, why = L.contract_mismatch(linux_mis, win_mis)
    if not ok:
        return fail(f"contract {why}")

    silent_ok, silent_why = L.contract_mismatch(linux_mis, silent)
    if silent_ok:
        return fail("silent Windows mutant must be rejected by contract")
    if silent_why != "windows-hit-without-warning":
        return fail(f"silent mutant reason {silent_why}")
    if silent.ok and not silent.warnings:
        pass
    else:
        return fail(f"mutant should be a silent hit {silent}")

    second = H.second_shell_windows()
    if not second["agree"]:
        return fail(f"posix vs nt Windows-policy diverge {second}")
    if not second["posix"]["warnings"] or not second["nt"]["warnings"]:
        return fail("second-shell warning stream empty")

    file_mis = L.lookup(H.ROOT, H.MISMATCH_FILE, L.WINDOWS)
    if not file_mis.ok or not file_mis.names_mismatch("Skills", "skills"):
        return fail(f"file-level Skills/ must warn {file_mis}")

    print(
        json.dumps(
            {
                "probe": "probe2-windows-warning-matrix",
                "independent_listdir": names,
                "windows_mismatch_ok": True,
                "windows_resolved": win_mis.resolved,
                "warning_stream": win_mis.warnings,
                "warning_names_Skills_and_skills": True,
                "silent_mutant_rejected": True,
                "silent_mutant_why": silent_why,
                "second_shell_agree": True,
                "second_shell_note": second["note"],
                "contract": why,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0195-probe2 Windows warning stream and silent-mutant control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
