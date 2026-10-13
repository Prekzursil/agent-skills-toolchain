#!/usr/bin/env python
"""Both-states selftest for postmodelswitch-ledger/log.py.

Fires-state: a model-switch payload MUST append a ledger row.
Benign-state: malformed/empty stdin MUST exit 0 and append nothing.
Run: python selftest.py  (uses a temp ledger; never touches the live one)
"""
import subprocess, sys, os, json, tempfile, pathlib

HERE = pathlib.Path(__file__).parent
MOD = HERE / "log.py"

def run(payload, ledger):
    env = dict(os.environ, PMODELSWITCH_LEDGER=str(ledger))
    p = subprocess.run([sys.executable, str(MOD)], input=payload,
                       capture_output=True, text=True, env=env)
    rows = []
    if ledger.exists():
        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    return p.returncode, rows

with tempfile.TemporaryDirectory() as td:
    led = pathlib.Path(td) / "sw.jsonl"
    rc1, rows1 = run(json.dumps({"fromModel": "claude-opus-5-5", "toModel": "claude-opus-4-8",
                                 "session_id": "t1", "reason": "safeguard_fallback"}), led)
    rc2, rows2 = run("not-json{{{", led)
    rc3, rows3 = run("", led)
    ok_fire = rc1 == 0 and len(rows1) == 1 and rows1[0]["toModel"] == "claude-opus-4-8"
    ok_benign = rc2 == 0 and rc3 == 0 and len(rows2) == 1  # malformed added nothing
    print(f"  {'PASS' if ok_fire else 'FAIL'} fires on switch payload (row logged, exit 0)")
    print(f"  {'PASS' if ok_benign else 'FAIL'} silent on malformed/empty stdin (exit 0, no row)")
    print("SUCCESS:postmodelswitch-ledger.selftest" if ok_fire and ok_benign
          else "FAILED:postmodelswitch-ledger.selftest")
    sys.exit(0 if ok_fire and ok_benign else 1)
