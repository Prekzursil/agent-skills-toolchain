#!/usr/bin/env python3
"""Named probe 2: rotation bounds, negative-control grep, control-char injection.

Mechanically different from probe 1 (which greps a redacted secret and parses
one record). This probe:
  * measures OS file count and sizes against the declared rotation caps
  * disables the filter and asserts grep DOES find the planted body
  * injects LF/CR/NEL/LS/PS and asserts json.loads still sees exactly one record
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import jsonl_log as jl  # noqa: E402

PLANTED_SECRET = "ghp_SYNTHETICNOTAREALTOKENIMP0056xx"


def grep_rc(path: Path, body: str) -> int:
    proc = subprocess.run(
        ["grep", "-F", body, str(path)],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0056-p2-") as tmp:
        tmp_path = Path(tmp)

        # --- rotation bounds (OS measurement, not the logger's own boolean) ---
        rot_path = tmp_path / "rotate.jsonl"
        max_bytes, max_files = 400, 3
        rot = jl.JsonlLogger(
            rot_path,
            unit_id="IMP-0056",
            max_bytes=max_bytes,
            max_files=max_files,
        )
        for i in range(80):
            rot.write("PLUGIN.LOG.INFO", event="rotate", seq=i, pad="x" * 40)
        sink_files = list(tmp_path.glob("rotate.jsonl*"))
        sizes = [p.stat().st_size for p in sink_files]
        if len(sink_files) > max_files:
            print(f"FAILED:IMP-0056-probe2 file_count={len(sink_files)} > {max_files}")
            return 1
        if any(s > max_bytes for s in sizes):
            print(f"FAILED:IMP-0056-probe2 oversize {sizes}")
            return 1
        if Path(f"{rot_path}.{max_files}").exists():
            print("FAILED:IMP-0056-probe2 generation past max_files exists")
            return 1

        # --- negative control: filter off, grep must fire ---
        neg_path = tmp_path / "neg.jsonl"
        jl.JsonlLogger(neg_path, unit_id="IMP-0056", redact=False).write(
            "PLUGIN.LOG.INFO",
            event="neg-control",
            message=f"token={PLANTED_SECRET}",
        )
        if grep_rc(neg_path, PLANTED_SECRET) != 0:
            print("FAILED:IMP-0056-probe2 negative control: grep did not find body")
            return 1
        on_path = tmp_path / "on.jsonl"
        jl.JsonlLogger(on_path, unit_id="IMP-0056", redact=True).write(
            "PLUGIN.LOG.INFO",
            event="pos-control",
            message=f"token={PLANTED_SECRET}",
        )
        if grep_rc(on_path, PLANTED_SECRET) != 1:
            print("FAILED:IMP-0056-probe2 filter-on still leaked body")
            return 1

        # --- control-character injection cannot forge a record boundary ---
        inj_path = tmp_path / "inject.jsonl"
        payload = (
            "before\n"
            '{"error_code":"FORGED","unit_id":"EVIL"}\n'
            "after\u0085mid\u2028line\u2029end\r"
        )
        jl.JsonlLogger(inj_path, unit_id="IMP-0056").write(
            "PLUGIN.LOG.INFO",
            event="inject",
            message=payload,
        )
        raw = inj_path.read_bytes()
        text = raw.decode("ascii")
        nonempty = [ln for ln in text.split("\n") if ln != ""]
        if len(nonempty) != 1:
            print(f"FAILED:IMP-0056-probe2 forged lines={len(nonempty)}")
            return 1
        rec = json.loads(nonempty[0])
        if rec.get("error_code") == "FORGED" or rec.get("unit_id") == "EVIL":
            print("FAILED:IMP-0056-probe2 forged record accepted")
            return 1
        if rec.get("error_code") != "PLUGIN.LOG.INFO":
            print("FAILED:IMP-0056-probe2 injected error_code", rec.get("error_code"))
            return 1
        if b"\n" in raw[:-1]:
            print("FAILED:IMP-0056-probe2 interior LF survived encode")
            return 1

    out = {
        "probe": "probe2-rotation-boundary",
        "unit_id": "IMP-0056",
        "rotation_file_count": len(sink_files),
        "rotation_max_files": max_files,
        "rotation_sizes": sizes,
        "rotation_max_bytes": max_bytes,
        "negative_control_grep_found_body": True,
        "filter_on_grep_missed_body": True,
        "injection_record_count": 1,
        "forged_record_rejected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0056-probe2 rotation bounds, negative control, record boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
