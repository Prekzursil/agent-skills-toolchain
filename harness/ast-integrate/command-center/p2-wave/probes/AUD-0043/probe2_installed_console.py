#!/usr/bin/env python3
"""Named probe 2: wheel-install console script + include-list both-states control."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import scenario as S  # noqa: E402


def main() -> int:
    art = S.REPO / S.OUT_REL
    if not art.is_file():
        print("FAILED:AUD-0043-probe2 artifact missing")
        return 1
    doc = json.loads(art.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:AUD-0043-probe2 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0043-p2-") as tmp:
        root = Path(tmp)
        good_src = H.copy_pkg(root / "src-good", mutant=False)
        mutant_src = H.copy_pkg(root / "src-mutant", mutant=True)
        installed_good = H.run_installed(good_src, root / "inst-good")
        installed_mutant = H.run_installed(mutant_src, root / "inst-mutant")

    if not installed_good["console_ok"]:
        print("FAILED:AUD-0043-probe2 installed console on good package failed")
        print(json.dumps(installed_good, indent=2)[:2000])
        return 1
    if not installed_good["script_exists"]:
        print("FAILED:AUD-0043-probe2 console script missing after install")
        return 1
    if not installed_good["script_outside_repo"] or not installed_good["venv_outside_repo"]:
        print("FAILED:AUD-0043-probe2 venv or script inside repo")
        return 1
    if installed_good["console_repo_hits"]:
        print("FAILED:AUD-0043-probe2 repo on sys.path", installed_good["console_repo_hits"])
        return 1
    if installed_mutant["console_ok"]:
        print("FAILED:AUD-0043-probe2 include-omit mutant stayed GREEN after install")
        print(json.dumps(installed_mutant, indent=2)[:2000])
        return 1
    err = str(installed_mutant.get("report_error") or "")
    stderr = str((installed_mutant.get("console") or {}).get("stderr") or "")
    blob = err + "\n" + stderr
    if "aud0043_extra" not in blob and "ModuleNotFoundError" not in blob:
        print("FAILED:AUD-0043-probe2 mutant did not name the omitted module")
        print(blob[-800:])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-installed-console",
                "unit_id": S.UNIT,
                "pass": True,
                "good_console_ok": True,
                "mutant_console_ok": False,
                "both_states": True,
                "wheel_good": installed_good.get("wheel_name"),
                "wheel_mutant": installed_mutant.get("wheel_name"),
                "script": installed_good.get("resolved_script_path"),
                "mutant_error": installed_mutant.get("report_error"),
            },
            sort_keys=True,
        )
    )
    print(
        "good_console=GREEN mutant_console=RED "
        f"error={installed_mutant.get('report_error')}"
    )
    print("SUCCESS:AUD-0043-probe2 installed console and exclude-module control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
