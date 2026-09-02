#!/usr/bin/env python3
"""Probe 1: PATH shim is first proven to catch a known spawn, then used.

Detector control: production render spawn count N; insert one extra `true`
spawn; shim count becomes N+1. A grep of statusline.py for jq/git/sleep is
recorded and is NOT the detector (those words appear in comments).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.hud.spawn_measure import (  # noqa: E402
    install_shims,
    prove_shim_catches_known_spawn,
    run_statusline,
)
from tools.hud.statusline import SPAWN_CEILING  # noqa: E402

UID = "TST-0238"
PAYLOAD = HERE / "fixtures" / "payload.json"
RENDERER = REPO / "tools" / "hud" / "statusline.py"


def grep_mentions(src: str) -> dict:
    return {
        "jq": len(re.findall(r"\bjq\b", src)),
        "git": len(re.findall(r"\bgit\b", src)),
        "sleep": len(re.findall(r"\bsleep\b", src)),
        "true": len(re.findall(r"\btrue\b", src)),
    }


def main() -> int:
    src = RENDERER.read_text(encoding="utf-8")
    grep = grep_mentions(src)
    with tempfile.TemporaryDirectory(prefix="tst0238-p1-") as tmp_s:
        tmp = Path(tmp_s)
        shim_dir = tmp / "shim"
        log_path = tmp / "spawn.log"
        install_shims(shim_dir, log_path)

        proven = prove_shim_catches_known_spawn(shim_dir, log_path)
        if not proven["caught"] or proven["shim_count"] < 1:
            print(json.dumps({"probe": "probe1", "pass": False, "proven": proven}, sort_keys=True))
            print("FAILED:TST-0238-probe1 shim did not catch a known `true` spawn")
            return 1

        log_path.write_text("", encoding="utf-8")
        production = run_statusline(
            REPO,
            extra_args=[
                "--payload",
                str(PAYLOAD),
                "--state-dir",
                str(tmp / "st-prod"),
                "--debounce-ms",
                "0",
            ],
            shim_dir=shim_dir,
            log_path=log_path,
        )
        n_prod = int(production["shim_count"])

        log_path.write_text("", encoding="utf-8")
        injected = run_statusline(
            REPO,
            extra_args=[
                "--payload",
                str(PAYLOAD),
                "--state-dir",
                str(tmp / "st-inj"),
                "--debounce-ms",
                "0",
                "--inject-spawn",
                "true",
            ],
            shim_dir=shim_dir,
            log_path=log_path,
        )
        n_inj = int(injected["shim_count"])

    incremented = n_inj == n_prod + 1
    under = n_prod <= SPAWN_CEILING
    payload = {
        "probe": "probe1-shim-detector-control",
        "unit_id": UID,
        "pass": bool(
            proven["caught"]
            and incremented
            and under
            and n_prod == 0
            and production["exit_code"] == 0
            and injected["exit_code"] == 0
        ),
        "detector": "PATH-shim-spawn-log",
        "grep_of_script_is_not_the_detector": True,
        "grep_mentions_in_statusline_py": grep,
        "grep_would_be_nonzero": any(v > 0 for v in grep.values()),
        "shim_proven_known_spawn": proven,
        "production_shim_count": n_prod,
        "injected_shim_count": n_inj,
        "incremented_by_one": incremented,
        "production_under_ceiling": under,
        "ceiling": SPAWN_CEILING,
        "production_stdout": production["stdout"].strip(),
        "injected_shim_names": injected["shim_names"],
        "production_exit": production["exit_code"],
        "injected_exit": injected["exit_code"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0238-probe1 detector control did not increment a proven shim")
        return 1
    if not payload["grep_would_be_nonzero"]:
        print("FAILED:TST-0238-probe1 expected historical jq/sleep words in comments")
        return 1
    print(
        f"known_spawn={proven['shim_count']} production={n_prod} "
        f"injected={n_inj} increment={incremented}"
    )
    print("SUCCESS:TST-0238-probe1 PATH shim proven and detector control increments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
