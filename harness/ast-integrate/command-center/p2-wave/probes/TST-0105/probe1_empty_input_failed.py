#!/usr/bin/env python3
"""Named probe 1: empty-input run is FAILED and reports no number.

Signal 1 of TST-0105. Both-states in one process: planted empty FAILS with
value_ms=None and work not invoked; nonempty emits a number with n_inputs.
The naive timer is the detector control that still greened the empty case.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0105.json"
HARNESS_DIR = REPO / "hooks" / "harness-bench"
FIX = HARNESS_DIR / "fixtures"
sys.path.insert(0, str(HARNESS_DIR))

import harness as H  # noqa: E402

HIST_EMPTY = FIX / "historical-empty-pair.json"
HIST_OK = FIX / "historical-nonempty-pair.json"


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(HARNESS_DIR / "harness.py"), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0105-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0105-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0105-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0105-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0105" not in text:
        print("FAILED:TST-0105-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "TST-0105":
        print(f"FAILED:TST-0105-probe1 unit_id {doc.get('unit_id')}")
        return 1

    called = {"n": 0}

    def work(inputs):
        called["n"] += 1
        return H.default_work(inputs)

    empty = H.measure("planted-empty", [], work)
    nonempty = H.measure("planted-nonempty", ["a", "b", "c"], work)
    naive = H.naive_measure("router-eval", [])

    if empty["ok"] or empty["value_ms"] is not None:
        print("FAILED:TST-0105-probe1 empty run emitted a number")
        print(json.dumps(empty, indent=2)[:2000])
        return 1
    if empty["n_inputs"] != 0 or empty["reason"] != H.REASON_EMPTY:
        print(f"FAILED:TST-0105-probe1 empty row {empty}")
        return 1
    if H.VALUE_TOKEN in empty["printed"]:
        print(f"FAILED:TST-0105-probe1 empty printed a value: {empty['printed']}")
        return 1
    if empty["work_invoked"] or called["n"] != 1:
        print(
            "FAILED:TST-0105-probe1 work invoked on empty "
            f"or nonempty did not run: invoked={empty['work_invoked']} n={called['n']}"
        )
        return 1
    if not nonempty["ok"] or nonempty["n_inputs"] != 3:
        print(f"FAILED:TST-0105-probe1 nonempty failed: {nonempty}")
        return 1
    if H.VALUE_TOKEN not in nonempty["printed"]:
        print(f"FAILED:TST-0105-probe1 nonempty missing value: {nonempty['printed']}")
        return 1
    if f"{H.N_TOKEN}3" not in nonempty["printed"]:
        print(f"FAILED:TST-0105-probe1 nonempty missing n_inputs: {nonempty['printed']}")
        return 1
    if not naive["ok"] or naive["value_ms"] is None or H.N_TOKEN in naive["printed"]:
        print(f"FAILED:TST-0105-probe1 naive control did not green-without-n: {naive}")
        return 1

    proc_bad = _cli(["--cases-json", str(HIST_EMPTY), "--json"])
    if proc_bad.returncode == 0:
        print("FAILED:TST-0105-probe1 historical empty pair exited 0")
        print(proc_bad.stdout[-2000:])
        return 1
    try:
        body_bad = json.loads(proc_bad.stdout)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0105-probe1 historical empty json {exc}")
        print(proc_bad.stdout[-2000:])
        return 1
    names = [r["name"] for r in body_bad.get("rows") or []]
    if names != list(H.HISTORICAL_EMPTY_GREENS):
        print(f"FAILED:TST-0105-probe1 historical names {names}")
        return 1
    if any(r.get("value_ms") is not None for r in body_bad["rows"]):
        print("FAILED:TST-0105-probe1 historical empty leaked a number")
        print(json.dumps(body_bad, indent=2)[:2000])
        return 1

    proc_ok = _cli(["--cases-json", str(HIST_OK)])
    if proc_ok.returncode != 0:
        print("FAILED:TST-0105-probe1 nonempty pair failed")
        print((proc_ok.stdout + proc_ok.stderr)[-2000:])
        return 1
    for line in (proc_ok.stdout or "").splitlines():
        if H.VALUE_TOKEN in line and H.N_TOKEN not in line:
            print(f"FAILED:TST-0105-probe1 number without n_inputs: {line}")
            return 1

    payload = {
        "adjudicated": True,
        "empty_failed": True,
        "empty_value_ms": empty["value_ms"],
        "empty_printed": empty["printed"],
        "nonempty_n_inputs": nonempty["n_inputs"],
        "nonempty_printed": nonempty["printed"],
        "naive_still_reports_number": True,
        "historical_empty_exit": proc_bad.returncode,
        "historical_empty_names": names,
        "negative_control_same_run": True,
        "pass": True,
        "probe": "probe1-empty-input-failed",
        "unit_id": "TST-0105",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "empty_ok=False nonempty_ok=True naive_greens=True "
        "same_run_negative_control=True"
    )
    print("SUCCESS:TST-0105-probe1 empty-input is failed not reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
