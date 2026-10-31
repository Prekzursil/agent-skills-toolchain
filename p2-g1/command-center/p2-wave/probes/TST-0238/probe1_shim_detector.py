#!/usr/bin/env python3
"""TST-0238 probe 1: the PATH shim is the detector, proven on a known spawn.

Windows adaptation: CreateProcess only resolves *.exe, so the shim is a
tiny compiled true.exe (shim_exe.py) that logs its own name. PASS requires:
  * the shim FIRST catches a known `true` spawn via PATH resolution
    (caller PATH swap; shim_count 0 -> 1);
  * one production render performs 0 external PATH-visible spawns, under
    the LIVE SPAWN_CEILING read from tools/hud/statusline.py;
  * inserting one known extra spawn increments the count by exactly one;
  * a text grep of the renderer is shown NOT to be a detector (it counts
    comment words), while the shim count stays the real budget.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import shim_exe  # noqa: E402
from hud import spawn_measure  # noqa: E402
from hud.statusline import SPAWN_CEILING  # noqa: E402

PAYLOAD = HERE / "fixtures" / "payload.json"


def clear_log(log_path: Path) -> None:
    log_path.write_text("", encoding="utf-8")


def read_names(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return []
    return [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> int:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tst0238-probe1-") as td:
        built = shim_exe.compile_shims(Path(td))
        checks["shim_exe_compiled"] = built["ok"] is True
        if not built["ok"]:
            print(json.dumps({"probe": "probe1-shim-detector-control", "unit_id": "TST-0238",
                              "checks": checks, "pass": False, "reason": built["reason"]}))
            return 1
        shim_dir: Path = built["shim_dir"]
        log_path = Path(td) / "spawn-log.txt"
        clear_log(log_path)

        # 1. PROOF: the shim catches a known `true` spawn via PATH resolution.
        old_path = os.environ["PATH"]
        os.environ["PATH"] = str(shim_dir) + os.pathsep + old_path
        os.environ["TST0238_SHIM_LOG"] = str(log_path)
        try:
            p = subprocess.run(["true"], capture_output=True)
            proof_names = read_names(log_path)
            checks["shim_proven_known_spawn"] = p.returncode == 0 and proof_names == ["true"]
            checks["shim_count_after_proof_is_one"] = len(proof_names) == 1
            clear_log(log_path)

            # 2. production render: external PATH-visible spawns per render.
            prod = spawn_measure.run_statusline(
                REPO,
                extra_args=["--payload", PAYLOAD.as_posix()],
                shim_dir=shim_dir, log_path=log_path,
            )
            checks["production_render_exit_zero"] = prod["exit_code"] == 0
            checks["production_shim_count_zero"] = prod["shim_count"] == 0
            checks["production_under_ceiling"] = prod["shim_count"] <= SPAWN_CEILING
            clear_log(log_path)

            # 3. detector control: insert ONE known extra spawn.
            inj = spawn_measure.run_statusline(
                REPO,
                extra_args=["--payload", PAYLOAD.as_posix(), "--inject-spawn", "true"],
                shim_dir=shim_dir, log_path=log_path,
            )
            checks["injected_exit_zero"] = inj["exit_code"] == 0
            checks["injected_shim_count_one"] = inj["shim_count"] == 1
            checks["incremented_by_one"] = inj["shim_count"] == prod["shim_count"] + 1
            checks["injected_shim_names_true"] = inj["shim_names"] == ["true"]
        finally:
            os.environ["PATH"] = old_path
            os.environ.pop("TST0238_SHIM_LOG", None)

        # 4. grep-of-script is NOT the detector: it counts comment words.
        src = (REPO / "tools" / "hud" / "statusline.py").read_text(encoding="utf-8")
        grep_map = {w: src.count(w) for w in ("git", "jq", "sleep", "true")}
        checks["grep_would_be_nonzero"] = any(v > 0 for v in grep_map.values())

        bools = {k: v for k, v in checks.items() if isinstance(v, bool)}
        out = {
            "probe": "probe1-shim-detector-control",
            "unit_id": "TST-0238",
            "subject": "tools/hud/statusline.py",
            "detector": "PATH shim spawn log (compiled exe shim, proven on known true spawn)",
            "not_a_detector": "text grep of the renderer script",
            "grep_of_script_is_not_the_detector": True,
            "grep_would_be_nonzero": checks["grep_would_be_nonzero"],
            "grep_mentions_in_statusline_py": grep_map,
            "production_shim_count": prod["shim_count"],
            "injected_shim_count": inj["shim_count"],
            "incremented_by_one": checks["incremented_by_one"],
            "production_exit": prod["exit_code"],
            "injected_exit": inj["exit_code"],
            "production_stdout": prod["stdout"][:120],
            "ceiling": SPAWN_CEILING,
            "production_under_ceiling": checks["production_under_ceiling"],
            "shim_proven_known_spawn": {"caught": checks["shim_proven_known_spawn"],
                                        "shim_count": 1, "shim_names": ["true"]},
            "checks": checks,
            "pass": all(bools.values()),
        }
        (HERE / "probe1_shim_detector.raw.txt").write_text(
            json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(out, sort_keys=True))
        return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
