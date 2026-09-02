#!/usr/bin/env python3
"""Probe 2: remove deciding-rule id; CLI reports UNKNOWN rather than guessing.

Catalog tests_required[1]. Both states:
  * intact artifact names rule.chair-override for D2 (reject-majority tally)
  * stripped artifact reports UNKNOWN for every decision, including D1 where
    a majority guess would coincidentally match the stored rule
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
sys.path.insert(0, str(REPO))

from fixture import (  # noqa: E402
    RULE_CHAIR,
    guess_majority_rule,
    recorded_council,
    strip_deciding_rules,
)

UID = "IMP-0316"
RECEIPT = REPO / "command-center" / "receipts" / f"{UID}.json"
CLI = REPO / "tools" / "council" / "cli" / "audit.py"


def run_cli(artifact: Path, *args: str) -> tuple[int, dict]:
    cmd = [sys.executable, "-B", str(CLI), "--offline", *args, str(artifact)]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    if proc.returncode != 0 and not parsed:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-1200:]
        print(f"FAILED:{UID}-probe2 cli rc={proc.returncode} {tail}")
    return proc.returncode, parsed


def write_json(doc: dict, path: Path) -> Path:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


def check_receipt() -> str | None:
    if not RECEIPT.is_file():
        return "receipt missing"
    text = RECEIPT.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    if f"SUCCESS:{UID}" not in text:
        return "sentinel absent"
    return None


def main() -> int:
    intact = recorded_council()
    stripped = strip_deciding_rules(intact)
    with tempfile.TemporaryDirectory(prefix="imp0316-nc-") as tmp:
        root = Path(tmp)
        good_path = write_json(intact, root / "intact.json")
        bad_path = write_json(stripped, root / "stripped.json")

        rc_g, good = run_cli(good_path, "lineage")
        rc_b, bad = run_cli(bad_path, "lineage")
        if rc_g != 0 or rc_b != 0:
            return 1

        good_by = {e["decision_id"]: e for e in good.get("entries") or []}
        bad_by = {e["decision_id"]: e for e in bad.get("entries") or []}
        if set(good_by) != {"D1", "D2", "D3"} or set(bad_by) != {"D1", "D2", "D3"}:
            print(f"FAILED:{UID}-probe2 missing decisions {set(good_by)} {set(bad_by)}")
            return 1

        if good_by["D2"].get("deciding_rule_id") != RULE_CHAIR:
            print(
                f"FAILED:{UID}-probe2 intact D2 rule "
                f"{good_by['D2'].get('deciding_rule_id')}"
            )
            return 1

        d2_tally = good_by["D2"].get("tally") or {}
        guessed = guess_majority_rule(d2_tally)
        if guessed == RULE_CHAIR:
            print(f"FAILED:{UID}-probe2 guesser collapsed onto chair rule")
            return 1
        if guessed != "rule.majority-reject":
            print(f"FAILED:{UID}-probe2 unexpected majority guess {guessed}")
            return 1

        unknown_ids = []
        for did, entry in bad_by.items():
            rule = entry.get("deciding_rule_id")
            if rule != "UNKNOWN":
                print(f"FAILED:{UID}-probe2 stripped {did} reported {rule} not UNKNOWN")
                return 1
            if rule == guessed:
                print(f"FAILED:{UID}-probe2 stripped {did} guessed {guessed}")
                return 1
            unknown_ids.append(did)

        d1_guess = guess_majority_rule(good_by["D1"].get("tally") or {})
        if d1_guess != good_by["D1"].get("deciding_rule_id"):
            print(f"FAILED:{UID}-probe2 D1 is not the coincidental-majority case")
            return 1
        if bad_by["D1"].get("deciding_rule_id") != "UNKNOWN":
            print(f"FAILED:{UID}-probe2 stripped D1 was guessed")
            return 1

        if bad.get("live_model_call") is not False:
            print(f"FAILED:{UID}-probe2 live_model_call on stripped artifact")
            return 1

        rec_err = check_receipt()
        if rec_err:
            print(f"FAILED:{UID}-probe2 {rec_err}")
            return 1

        report = {
            "probe": "probe2-unknown-rule",
            "unit_id": UID,
            "pass": True,
            "intact_d2_rule": good_by["D2"]["deciding_rule_id"],
            "stripped_rules": {
                k: v.get("deciding_rule_id") for k, v in bad_by.items()
            },
            "majority_guess_for_d2": guessed,
            "guess_differs_from_stored_d2": guessed != RULE_CHAIR,
            "stripped_reported_unknown": unknown_ids,
            "did_not_guess": all(
                v.get("deciding_rule_id") == "UNKNOWN" for v in bad_by.values()
            ),
            "silent_on_good": good_by["D2"]["deciding_rule_id"] == RULE_CHAIR,
            "fired_on_bad": all(
                v.get("deciding_rule_id") == "UNKNOWN" for v in bad_by.values()
            ),
        }
        print(json.dumps(report, sort_keys=True, ensure_ascii=True))
        print(
            f"SUCCESS:{UID}-probe2 missing rule id reports UNKNOWN rather than guessing"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
