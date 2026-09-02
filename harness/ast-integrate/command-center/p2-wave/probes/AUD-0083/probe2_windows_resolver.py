#!/usr/bin/env python3
"""Probe 2: Windows pwsh7 bare-invocation resolver. Must not read shebang."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0083-script-interpreter-audit.json"
SENTINEL = (
    "SUCCESS:AUD-0083 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def main() -> int:
    ctrl = E.control_pair()
    with_sb = HERE / "fixtures" / "control" / "with-shebang.sh"
    honest_bare = ctrl["honest_bare_with_shebang"]["outcome"]
    honest_explicit = ctrl["honest_explicit_bash"]["outcome"]
    mutant = ctrl["shebang_reading_mutant"]["outcome"]
    ext_mutant = ctrl["extension_implies_bash_mutant"]["outcome"]

    linux_exec = None
    if os.name == "posix" and with_sb.is_file():
        try:
            proc = subprocess.run(
                [str(with_sb)],
                capture_output=True,
                text=True,
                check=False,
            )
            linux_exec = {
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "").strip(),
                "note": "POSIX honoured the shebang; this is not the Windows answer",
            }
        except OSError as exc:
            linux_exec = {"error": str(exc)}

    print(
        json.dumps(
            {
                "honest_bare": honest_bare,
                "honest_explicit_bash": honest_explicit,
                "shebang_mutant_bare": mutant,
                "extension_mutant_bare": ext_mutant,
                "control_pass": ctrl["control_pass"],
                "reads_shebang": ctrl["honest_bare_with_shebang"].get("reads_shebang"),
                "pwsh_present": ctrl["pwsh_present"],
                "linux_exec": linux_exec,
            },
            sort_keys=True,
        )
    )

    if honest_bare != "FAILURE":
        print("FAILED:AUD-0083-probe2 bare .sh on Windows was not FAILURE")
        return 1
    if honest_explicit != "SUCCESS":
        print("FAILED:AUD-0083-probe2 explicit bash was not SUCCESS")
        return 1
    if honest_bare == "SUCCESS" and honest_explicit == "SUCCESS":
        print("FAILED:AUD-0083-probe2 resolver passed both; it is reading the shebang")
        return 1
    if not ctrl["control_pass"]:
        print("FAILED:AUD-0083-probe2 control_pass is false")
        return 1
    if ctrl["honest_bare_with_shebang"].get("reads_shebang"):
        print("FAILED:AUD-0083-probe2 honest resolver reads_shebang=true")
        return 1
    if mutant != "SUCCESS":
        print("FAILED:AUD-0083-probe2 shebang mutant did not take the bait")
        return 1
    if not ctrl["shebang_mutant_would_pass_both"]:
        print("FAILED:AUD-0083-probe2 shebang mutant was not shown to pass both")
        return 1
    if ext_mutant != "SUCCESS":
        print("FAILED:AUD-0083-probe2 extension mutant did not take the bait")
        return 1
    if ctrl["honest_bare_no_shebang"]["outcome"] != "FAILURE":
        print("FAILED:AUD-0083-probe2 no-shebang .sh was not FAILURE on Windows")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:AUD-0083-probe2 artifact state={doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:AUD-0083-probe2 completion sentinel absent")
            return 1
        print(f"artifact_state={doc.get('state')}")

    print(
        f"bare={honest_bare} explicit_bash={honest_explicit} "
        f"shebang_mutant={mutant} pwsh_present={ctrl['pwsh_present']}"
    )
    print("SUCCESS:AUD-0083-probe2 windows-pwsh7 resolver control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
