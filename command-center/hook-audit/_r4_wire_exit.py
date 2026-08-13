#!/usr/bin/env python3
r"""_r4_wire_exit.py -- settle, by EXECUTION, what `hooks/checkpoint/wire.py --check`
returns as a process exit code.

WHY. Two committed documents assert that `wire.py --check` "prints FAILED: and still
exits 0", and round 3 pointed round 4 at fixing that as a one-line defect inside
`hooks/**`. An independent verifier read `wire.py:228` (`return 0 if verdict == "CLEAN"
else 1`) plus `:232` (`sys.exit(main())`) and measured exit 1. This probe is the third,
mechanically different signal: it SPAWNS the script as a subprocess and reads the real
process exit status, on both trees.

THE CONTROL THAT MATTERS -- and the one the original claim lacked. Measuring one state
cannot tell "always 0" from "tracks the verdict"; measuring exit 1 once cannot tell
"always 1" from "tracks the verdict" either. So this probe drives BOTH verdicts through
the same binary using the script's own `--settings` / `--manifest` overrides:

  arm FINDING : the real surfaces (neither half wired)   -> expect FAILED: + rc 1
  arm CLEAN   : synthetic fixtures with both halves wired -> expect SUCCESS: + rc 0

`arms_discriminate` is true only when the two arms return DIFFERENT rcs. If they agree,
this probe measured nothing about the exit code and says so instead of publishing a
verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE = Path(os.path.expanduser("~")) / ".claude"

REPO_WIRE = REPO / "hooks" / "checkpoint" / "wire.py"
LIVE_WIRE = LIVE / "hooks" / "checkpoint" / "wire.py"

# The tokens wire.py looks for. Kept literal here on purpose: if wire.py's tokens change,
# the CLEAN arm stops going clean and `arms_discriminate` goes false -- a loud failure
# rather than a fixture that quietly stops exercising the WIRED branch.
PRECOMPACT_TOKEN = "hooks/checkpoint/precompact.py"
RECOVER_TOKEN = "hooks/checkpoint/recover.py"
RECOVER_CHECK = "checkpoint/recover.py"


def _run(script: Path, settings: Path, manifest: Path) -> dict:
    p = subprocess.run(
        [
            sys.executable,
            str(script),
            "--check",
            "--settings",
            str(settings),
            "--manifest",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    out = (p.stdout or "").strip()
    return {
        "rc": p.returncode,
        "has_failed_marker": "FAILED:checkpoint-wiring" in out,
        "has_success_marker": "SUCCESS:checkpoint-wiring" in out,
        "tail": out.splitlines()[-1][:160] if out else "",
    }


def _clean_fixtures(tmp: Path) -> tuple[Path, Path]:
    settings = tmp / "settings.json"
    manifest = tmp / "manifest.json"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreCompact": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'python "{PRECOMPACT_TOKEN}"',
                                }
                            ],
                        }
                    ],
                    "SessionStart": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'python "{RECOVER_TOKEN}"',
                                }
                            ],
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {"events": {"SessionStart": {"checks": [{"script": RECOVER_CHECK}]}}}
        ),
        encoding="utf-8",
    )
    return settings, manifest


def main() -> int:
    if not REPO_WIRE.is_file():
        print(f"FAILED:r4-wire-exit repo wire.py absent at {REPO_WIRE}")
        return 1

    real_settings = LIVE / "settings.json"
    real_manifest = LIVE / "hooks" / "_dispatch" / "manifest.json"

    result: dict = {
        "probe": "_r4_wire_exit.py",
        "source_of_the_refuted_claim": [
            "docs/hook-audit/HOOK-AUDIT.md (round 3 block) -- 'prints FAILED: and still exits 0 -- measured'",
            "docs/hook-audit/ROUND3-CORRECTIONS.md -- 'exits 0 (measured: EXIT=0 beside FAILED:checkpoint-wiring)'",
        ],
        "arms": {},
    }

    with tempfile.TemporaryDirectory(prefix="r4wire_") as td:
        tmp = Path(td)
        cs, cm = _clean_fixtures(tmp)
        for label, script in (("repo", REPO_WIRE), ("live", LIVE_WIRE)):
            if not script.is_file():
                result["arms"][label] = {"absent": True}
                continue
            result["arms"][label] = {
                "FINDING": _run(script, real_settings, real_manifest),
                "CLEAN": _run(script, cs, cm),
            }

    repo = result["arms"].get("repo", {})
    fin = repo.get("FINDING", {})
    cln = repo.get("CLEAN", {})
    result["repo_finding_rc"] = fin.get("rc")
    result["repo_clean_rc"] = cln.get("rc")
    result["arms_discriminate"] = bool(fin and cln and fin.get("rc") != cln.get("rc"))
    live = result["arms"].get("live", {})
    result["live_finding_rc"] = live.get("FINDING", {}).get("rc")
    result["live_clean_rc"] = live.get("CLEAN", {}).get("rc")

    # Fail closed: without discrimination the exit code is unmeasured, not "fine".
    if not result["arms_discriminate"]:
        result["verdict"] = "INCONCLUSIVE"
        (HERE / "R4-WIRE-EXIT.json").write_text(
            json.dumps(result, indent=1), encoding="utf-8"
        )
        print(json.dumps(result, indent=1))
        print(
            "FAILED:r4-wire-exit the two arms returned the same rc -- this probe cannot "
            "tell a constant exit code from one that tracks the verdict"
        )
        return 1

    result["verdict"] = (
        "EXIT_CODE_TRACKS_VERDICT"
        if (result["repo_finding_rc"] == 1 and result["repo_clean_rc"] == 0)
        else "DISCRIMINATES_BUT_UNEXPECTED_POLARITY"
    )
    result["claim_that_wire_py_exits_0_on_FAILED"] = "REFUTED"
    (HERE / "R4-WIRE-EXIT.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8"
    )
    print(json.dumps(result, indent=1))
    print("SUCCESS:r4-wire-exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
