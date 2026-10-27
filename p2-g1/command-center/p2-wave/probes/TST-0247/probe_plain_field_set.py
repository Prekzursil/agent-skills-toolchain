#!/usr/bin/env python3
"""TST-0247 probe A: the field set parsed from the live ``--plain`` output.

Runs ``python -m monitorcore.unified --plain --once`` as a real subprocess,
decodes the byte stream, asserts the surface is line-oriented (assistive
check: no CSI / cursor-addressing escapes anywhere in the bytes), parses the
exposed-information field set with the shared parser, and re-runs the whole
subprocess to prove the field set is deterministic. Writes its raw sidecar
and a measurement JSON next to itself.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fieldparse import parse_fields  # noqa: E402

MIN_FIELDS = 40
EXPECTED_PANES = {"codex", "agents", "workflows", "databricks", "mcp", "health"}


def plain_run() -> tuple[bytes, int]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "tools" / "monitorcore"), env.get("PYTHONPATH", "")]
    )
    p = subprocess.run(
        [sys.executable, "-m", "monitorcore.unified", "--plain", "--once"],
        cwd=str(REPO),
        capture_output=True,
        env=env,
        timeout=600,
    )
    return p.stdout, p.returncode


def main() -> int:
    checks: dict[str, bool] = {}
    raw_a, rc_a = plain_run()
    checks["subprocess_exit_0"] = rc_a == 0
    checks["nonempty_output"] = len(raw_a) > 0
    # Assistive check: line-oriented, screen-reader friendly — no escape bytes,
    # hence no cursor-addressing CSI sequences anywhere in the plain surface.
    checks["no_escape_bytes"] = b"\x1b" not in raw_a
    checks["no_csi_cursor_addressing"] = b"\x1b[" not in raw_a
    text_a = raw_a.decode("utf-8", errors="replace")
    lines_a = text_a.splitlines()
    pane_markers = {
        ln.split("=== pane ", 1)[1].split(" ===", 1)[0].strip()
        for ln in lines_a
        if ln.startswith("=== pane ")
    }
    checks["all_six_panes_dumped"] = pane_markers == EXPECTED_PANES
    fields_a = parse_fields(lines_a)
    checks["field_floor_met"] = len(fields_a) >= MIN_FIELDS
    checks["all_panes_expose_fields"] = all(
        any(f.startswith(pid + ".") for f in fields_a) for pid in EXPECTED_PANES
    )
    # Determinism: an identical second run parses to the identical field set.
    raw_b, rc_b = plain_run()
    fields_b = parse_fields(raw_b.decode("utf-8", errors="replace").splitlines())
    checks["second_run_exit_0"] = rc_b == 0
    checks["field_sets_deterministic"] = fields_a == fields_b

    out = {
        "probe": "probe_plain_field_set",
        "unit": "TST-0247",
        "signal": "(a) the field set parsed from the plain output",
        "plain_field_count": len(fields_a),
        "plain_field_set": sorted(fields_a),
        "pane_markers": sorted(pane_markers),
        "output_bytes": len(raw_a),
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-a-plain-field-set.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
