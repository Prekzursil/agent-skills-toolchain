#!/usr/bin/env python3
"""Named probe 2 (G-1 resume rewrite 2026-10-24): CI console-script exercise
via a real subprocess + byte-level reviewer reproduction.

Rewrite rationale: the inherited probe asserted receipt.runner_control, a key
the current reviewer-closed refute-generation receipt no longer carries. The
console exercise is kept and hardened: the console runner now runs in a FRESH
interpreter (subprocess), and the reviewer leg re-derives the falsification
mechanism at BYTE level (planted CRLF vs LF bytes) instead of trusting
test outcomes.

Mechanically different from probe 1: process-boundary execution + hex-level
data verification; no in-process revalidate() import for the verdict legs.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/BLD-0024.json"
RAW_OUT = HERE / "refute-probe2-console.raw.txt"
CHILD = HERE / "_probe2_child.py"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0024-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    # --- receipt cross-check: the runner-difference claim must be recorded ---
    claims = " ".join(str(e.get("claim") or "") for e in doc.get("evidence") or [])
    if "runner difference is exercised" not in claims:
        return fail("runner-difference evidence claim drifted")
    nc_ids = [nc.get("id") for nc in doc.get("negative_controls") or []]
    if "NC-RUNNER-IMPORT-PATH" not in nc_ids:
        return fail("NC-RUNNER-IMPORT-PATH no longer recorded")

    # --- subprocess console exercise ---
    CHILD.write_text(
        "import json, sys\n"
        "sys.path.insert(0, r'%s')\n"
        "from revalidate import run_condition\n"
        "as_is = run_condition('console', 'as_is')\n"
        "lf = run_condition('console', 'lf_norm')\n"
        "print(json.dumps({'as_is': as_is, 'lf_norm': lf}))\n" % str(HERE),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-B", str(CHILD)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return fail(f"console subprocess rc={proc.returncode}: {proc.stderr[-300:]}")
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    key = "test_crlf_text_lines"
    as_is, lf_norm = payload["as_is"][key], payload["lf_norm"][key]
    if as_is["outcome"] != "FAIL" or lf_norm["outcome"] != "PASS":
        return fail(f"console F-CRLF-1 as_is={as_is['outcome']} lf={lf_norm['outcome']}")
    pkg_con = payload["as_is"].get("test_packaging_in_tree_helper") or {}
    if pkg_con.get("outcome") != "FAIL":
        return fail("console packaging control no longer FAIL")
    CHILD.unlink(missing_ok=True)

    # --- byte-level reviewer reproduction (different mechanism) ---
    sys.path.insert(0, str(HERE))
    from revalidate import CRLF_FILES, plant_data  # noqa: E402

    hexrows = {}
    with tempfile.TemporaryDirectory(prefix="bld0024-p2-") as tmp:
        root = Path(tmp) / "data"
        plant_data(root, crlf=True)
        for name in CRLF_FILES:
            raw_bytes = (root / name).read_bytes()
            hexrows[name] = {
                "crlf_pairs": raw_bytes.count(b"\r\n"),
                "bare_lf": raw_bytes.count(b"\n") - raw_bytes.count(b"\r\n"),
            }
        plant_data(root, crlf=False)
        for name in CRLF_FILES:
            norm = (root / name).read_bytes()
            hexrows[name]["lf_only_crlf_pairs"] = norm.count(b"\r\n")
    for name, row in hexrows.items():
        if row["crlf_pairs"] < 1 or row["bare_lf"] != 0:
            return fail(f"planted {name} lacks pure CRLF bytes: {row}")
        if row["lf_only_crlf_pairs"] != 0:
            return fail(f"normalised {name} still carries CRLF bytes")
    reviewer = {
        "reviewer_id": "BLD-0024-probe2-console-reviewer (G-1 resume 2026-10-24)",
        "verdict": "PASS",
        "independent": True,
        "mechanism": "subprocess console run + byte-level CRLF census, not outcome trust",
        "console_f_crlf_1": {"as_is": as_is["outcome"], "lf_norm": lf_norm["outcome"]},
        "hexrows": hexrows,
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    RAW_OUT.write_text(
        json.dumps({"probe": "probe2-console-reviewer", "unit_id": "BLD-0024",
                    "generated": now, "pass": True, "reviewer": reviewer},
                   indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    print(json.dumps({"probe": "probe2-console-reviewer", "unit_id": "BLD-0024",
                      "console_rc": proc.returncode, "pass": True,
                      "console_crlf1_as_is": as_is["outcome"],
                      "console_crlf1_lf_norm": lf_norm["outcome"],
                      "packaging_gap_console_fail": True,
                      "reviewer_verdict": "PASS"}, sort_keys=True))
    print("SUCCESS:BLD-0024-probe2 console-script subprocess + byte-level reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
