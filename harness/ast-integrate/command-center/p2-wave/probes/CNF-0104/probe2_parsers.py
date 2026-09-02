#!/usr/bin/env python3
"""Named probe 2: parser matrix, independent of the artifact's written conclusion.

Re-derives last-wins vs error from the raw fixtures, then compares flags to
the recorded artifact. A reviewer who only re-reads findings does not count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import COMPLETION_SENTINEL, OUT_REL, UNIT_ID  # noqa: E402
from scenario import run_parser_matrix  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    live = run_parser_matrix()
    derived = {
        "json_loads_keeps_case_distinct_keys": live.get(
            "json_loads_keeps_case_distinct_keys"
        ),
        "json_loads_duplicate_exact_is_silent_last_wins": live.get(
            "json_loads_duplicate_exact_is_silent_last_wins"
        ),
        "strict_duplicate_errors": live.get("strict_duplicate_errors"),
        "casefold_consumer_silent_last_wins_on_Name_name": live.get(
            "casefold_consumer_silent_last_wins_on_Name_name"
        ),
        "silent_last_wins_distinguished_from_error": live.get(
            "silent_last_wins_distinguished_from_error"
        ),
        "control_survived": live.get("control_survived"),
    }
    print(json.dumps(derived, sort_keys=True))

    if derived["json_loads_keeps_case_distinct_keys"] is not True:
        print("FAILED:CNF-0104-probe2 json.loads dropped a case-distinct key")
        return 1
    if derived["json_loads_duplicate_exact_is_silent_last_wins"] is not True:
        print("FAILED:CNF-0104-probe2 json.loads did not last-wins on duplicate Name")
        return 1
    if derived["strict_duplicate_errors"] is not True:
        print("FAILED:CNF-0104-probe2 strict decoder did not error on duplicate")
        return 1
    if derived["casefold_consumer_silent_last_wins_on_Name_name"] is not True:
        print("FAILED:CNF-0104-probe2 casefold consumer did not collapse Name/name")
        return 1
    if derived["silent_last_wins_distinguished_from_error"] is not True:
        print("FAILED:CNF-0104-probe2 last-wins was not distinguished from error")
        return 1
    if derived["control_survived"] is not True:
        print("FAILED:CNF-0104-probe2 control keys did not survive")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0104-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:CNF-0104-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0104-probe2 self-declared {doc.get('state')}")
        return 1
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0104-probe2 completion_sentinel absent")
        return 1

    payload = doc.get("report") if isinstance(doc.get("report"), dict) else doc
    rec = payload.get("parsers") or {}
    for key, want in derived.items():
        if rec.get(key) != want:
            print(f"FAILED:CNF-0104-probe2 artifact drift on {key}: {rec.get(key)} != {want}")
            return 1
    answers = payload.get("answers") or {}
    if answers.get("parser_silently_keeps_only_one_case_distinct_key_json_loads") is not False:
        print("FAILED:CNF-0104-probe2 answers overclaim json.loads case collapse")
        return 1
    if answers.get("casefold_consumer_silently_keeps_one_of_Name_name") is not True:
        print("FAILED:CNF-0104-probe2 answers missed casefold collapse")
        return 1

    print("SUCCESS:CNF-0104-probe2 parser last-wins vs error and control keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
