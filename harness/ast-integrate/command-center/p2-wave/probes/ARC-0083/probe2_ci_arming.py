#!/usr/bin/env python3
"""CI-arming test: completeness is ON with a bare invocation.

The measured estate defect is validate.py's require_complete defaulting False
so deleting the entire defaults block still exits 0. This probe invokes the
ARC-0083 completeness tool with no arming flag against that same mutation
and asserts it still fails.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import completeness as C  # noqa: E402
import validate as val  # noqa: E402

TOOL = HERE / "completeness.py"
CONTRACT = REPO / C.CONTRACT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0083-probe2 {msg}")
    return 1


def run_bare(catalog_path: Path | None) -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-B",
        str(TOOL),
    ]
    if catalog_path is not None:
        cmd.extend(["--catalog", str(catalog_path)])
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    source = TOOL.read_text(encoding="utf-8")
    if "require_complete" in source or "require-complete" in source:
        return fail("disarm-flag-present in completeness.py")
    help_p = subprocess.run(
        [sys.executable, "-B", str(TOOL), "--help"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    help_text = (help_p.stdout or "") + (help_p.stderr or "")
    if "--require-complete" in help_text:
        return fail("help-exposes-disarm-flag")

    catalog = cat.load()
    live_code, live_out = run_bare(None)
    print(f"bare_live rc={live_code}")
    for line in live_out.splitlines()[-6:]:
        print(f"  {line}")
    if live_code == 0:
        return fail("bare live catalogue exited 0; completeness is not armed")
    missing_hist = [f for f in C.HISTORICAL_NINE if f not in live_out]
    if missing_hist:
        return fail(f"bare live output omitted historical fields {missing_hist}")

    mutant = copy.deepcopy(catalog)
    mutant.pop("defaults", None)
    v_off, _ = val.validate(mutant, require_complete=False)
    v_on, _ = val.validate(mutant, require_complete=True)
    off_fields = {row["check"] for row in v_off}
    on_fields = {row["check"] for row in v_on}
    print(f"validate.py mutant require_complete=False checks={sorted(off_fields)}")
    print(f"validate.py mutant require_complete=True checks={sorted(on_fields)}")
    defect_still = "V-FIELDS" not in off_fields
    print(f"validate.py_bare_still_misses_defaults_deletion={defect_still}")
    if "V-FIELDS" not in on_fields:
        return fail("validate.py require_complete=True did not fire V-FIELDS on mutation")

    with tempfile.TemporaryDirectory(prefix="arc0083-") as tmp:
        mutant_path = Path(tmp) / "catalog.json"
        mutant_path.write_text(
            json.dumps(mutant, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        mut_code, mut_out = run_bare(mutant_path)
        print(f"bare_mutant rc={mut_code}")
        for line in mut_out.splitlines()[-8:]:
            print(f"  {line}")
        if mut_code == 0:
            return fail("bare mutant (defaults deleted) exited 0")
        if "V-UNRESOLVED" not in mut_out and "unresolved" not in mut_out.lower():
            return fail("mutant did not report unresolved fields")
        if "FAILED:ARC-0083-completeness" not in mut_out:
            return fail("mutant missing FAILED sentinel")

    spec = json.loads(CONTRACT.read_text(encoding="utf-8")).get(
        "completeness_validator"
    ) or {}
    if spec.get("armed_by_default") is not True:
        return fail("contract armed_by_default is not true")
    if spec.get("disarm_flag") not in (None, ""):
        return fail(f"contract lists a disarm_flag {spec.get('disarm_flag')!r}")

    print(
        "armed_by_default=True "
        f"bare_live_fails={live_code != 0} "
        f"bare_mutant_fails={mut_code != 0} "
        f"validate_py_defect_present={defect_still}"
    )
    print("SUCCESS:ARC-0083-probe2 CI-arming bare invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
