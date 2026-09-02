#!/usr/bin/env python3
"""Named probe 2: independent stdout/JSON check that every number carries n_inputs.

Does not import harness.measure or format_row. Parses CLI --json with json.loads
and human lines with a regex. A naive green is identified by a value_ms token
without n_inputs on the same line.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0105.json"
HARNESS = REPO / "hooks" / "harness-bench" / "harness.py"
FIX = REPO / "hooks" / "harness-bench" / "fixtures"
HIST_EMPTY = FIX / "historical-empty-pair.json"
HIST_OK = FIX / "historical-nonempty-pair.json"
EMPTY = FIX / "empty.json"
NONEMPTY = FIX / "nonempty.json"

VALUE_RE = re.compile(r"value_ms=([0-9]+(?:\.[0-9]+)?)")
N_RE = re.compile(r"n_inputs=(\d+)")


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(HARNESS), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _numbers_without_n(text: str) -> list[str]:
    bad = []
    for line in (text or "").splitlines():
        if VALUE_RE.search(line) and not N_RE.search(line):
            bad.append(line)
    return bad


def _ok_lines_n(text: str) -> list[int]:
    found = []
    for line in (text or "").splitlines():
        vm = VALUE_RE.search(line)
        if not vm:
            continue
        nm = N_RE.search(line)
        if not nm:
            continue
        found.append(int(nm.group(1)))
    return found


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0105-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0105-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0105-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0105" not in text:
        print("FAILED:TST-0105-probe2 sentinel absent")
        return 1

    empty = _cli(["--name", "cli-empty", "--inputs-json", str(EMPTY), "--json"])
    if empty.returncode == 0:
        print("FAILED:TST-0105-probe2 empty CLI exited 0")
        print(empty.stdout[-2000:])
        return 1
    try:
        empty_body = json.loads(empty.stdout)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0105-probe2 empty stdout not json: {exc}")
        print(empty.stdout[-2000:])
        return 1
    empty_rows = empty_body.get("rows") or []
    if not empty_rows:
        print("FAILED:TST-0105-probe2 empty json had no rows")
        return 1
    for row in empty_rows:
        if row.get("value_ms") is not None:
            print(f"FAILED:TST-0105-probe2 empty json leaked value_ms={row.get('value_ms')}")
            return 1
        if int(row.get("n_inputs", -1)) != 0:
            print(f"FAILED:TST-0105-probe2 empty json n_inputs {row}")
            return 1
        printed = str(row.get("printed") or "")
        if VALUE_RE.search(printed):
            print(f"FAILED:TST-0105-probe2 empty printed a number: {printed}")
            return 1
        if not N_RE.search(printed):
            print(f"FAILED:TST-0105-probe2 empty printed missing n_inputs: {printed}")
            return 1
    human_empty = empty.stderr or ""
    if VALUE_RE.search(human_empty):
        print(f"FAILED:TST-0105-probe2 empty stderr leaked a number: {human_empty}")
        return 1

    ok = _cli(["--name", "cli-nonempty", "--inputs-json", str(NONEMPTY), "--json"])
    if ok.returncode != 0:
        print("FAILED:TST-0105-probe2 nonempty CLI failed")
        print((ok.stdout + ok.stderr)[-2000:])
        return 1
    ok_body = json.loads(ok.stdout)
    ok_rows = ok_body.get("rows") or []
    if not ok_rows:
        print("FAILED:TST-0105-probe2 nonempty json had no rows")
        return 1
    for row in ok_rows:
        n = int(row.get("n_inputs") or 0)
        val = row.get("value_ms")
        if n < 1:
            print(f"FAILED:TST-0105-probe2 nonempty n_inputs<{1}: {row}")
            return 1
        if not isinstance(val, (int, float)):
            print(f"FAILED:TST-0105-probe2 nonempty missing number: {row}")
            return 1
        printed = str(row.get("printed") or "")
        if not VALUE_RE.search(printed) or not N_RE.search(printed):
            print(f"FAILED:TST-0105-probe2 nonempty printed incomplete: {printed}")
            return 1

    pair = _cli(["--cases-json", str(HIST_OK)])
    if pair.returncode != 0:
        print("FAILED:TST-0105-probe2 historical nonempty failed")
        print((pair.stdout + pair.stderr)[-2000:])
        return 1
    human = pair.stdout or ""
    bad = _numbers_without_n(human)
    if bad:
        print(f"FAILED:TST-0105-probe2 human line has number without n_inputs: {bad}")
        return 1
    ns = _ok_lines_n(human)
    if len(ns) < 2 or any(n < 1 for n in ns):
        print(f"FAILED:TST-0105-probe2 expected two numbered lines with n>=1 got {ns} text={human!r}")
        return 1

    hist_empty = _cli(["--cases-json", str(HIST_EMPTY)])
    if hist_empty.returncode == 0:
        print("FAILED:TST-0105-probe2 historical empty pair exited 0")
        return 1
    hist_text = (hist_empty.stdout or "") + (hist_empty.stderr or "")
    if VALUE_RE.search(hist_text):
        print(f"FAILED:TST-0105-probe2 historical empty leaked value_ms: {hist_text}")
        return 1
    if hist_text.count("n_inputs=0") < 2:
        print(f"FAILED:TST-0105-probe2 historical empty missing two n_inputs=0: {hist_text}")
        return 1

    receipt_rows = ((doc.get("harness") or {}).get("live") or {}).get("rows") or []
    if receipt_rows:
        for row in receipt_rows:
            if row.get("value_ms") is not None and int(row.get("n_inputs") or 0) < 1:
                print(f"FAILED:TST-0105-probe2 receipt row number without n: {row}")
                return 1

    payload = {
        "empty_cli_exit": empty.returncode,
        "empty_json_value_ms": [r.get("value_ms") for r in empty_rows],
        "independent_parser": "json.loads + regex value_ms=/n_inputs=",
        "nonempty_n_inputs": [r.get("n_inputs") for r in ok_rows],
        "human_numbered_n_inputs": ns,
        "number_without_n_inputs_lines": bad,
        "pass": True,
        "probe": "probe2-cardinality-echo",
        "unit_id": "TST-0105",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"independent_json_and_regex=True empty_failed=True "
        f"every_number_has_n_inputs=True n={ns}"
    )
    print("SUCCESS:TST-0105-probe2 cardinality echoed beside every number")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
