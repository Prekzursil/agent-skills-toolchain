#!/usr/bin/env python3
"""Probe 1: two naive-0.95 fixtures that differ in dissent quality must split.

Also both-states: the gate FIRES on planted-bad (silent / reasoned dissent)
and is SILENT on known-good unanimous agreement. Negative control is printed
verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import consensus as C  # noqa: E402
import schema_check as S  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0069-what-number-is-0-95-consensus.md"
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0069-probe1 {msg}")
    return 1


def main() -> int:
    fx = C.fixtures()
    silent = C.tally_author(fx["naive-095-silent"])
    reasoned = C.tally_author(fx["naive-095-reasoned-dissent"])
    token = C.tally_author(fx["naive-095-token-dissent"])
    good = C.tally_author(fx["known-good-unanimous"])

    print(
        f"silent naive={silent['naive_fraction']} ge095={silent['naive_ge_095']} "
        f"ok={silent['stopping_ok']} codes={silent['blocking_codes']}"
    )
    print(
        f"reasoned naive={reasoned['naive_fraction']} ge095={reasoned['naive_ge_095']} "
        f"ok={reasoned['stopping_ok']} codes={reasoned['blocking_codes']}"
    )
    print(
        f"token naive={token['naive_fraction']} ge095={token['naive_ge_095']} "
        f"ok={token['stopping_ok']} codes={token['blocking_codes']}"
    )
    print(
        f"good naive={good['naive_fraction']} ge095={good['naive_ge_095']} "
        f"ok={good['stopping_ok']} codes={good['blocking_codes']}"
    )

    if silent["naive_fraction"] != "19/20" or reasoned["naive_fraction"] != "19/20":
        return fail("naive collision not 19/20 on both fixtures")
    if not (silent["naive_ge_095"] and reasoned["naive_ge_095"]):
        return fail("naive formula did not reach 0.95 on both fixtures")
    if silent["blocking_codes"] == reasoned["blocking_codes"]:
        return fail("silent and reasoned dissent not distinguishable")
    if silent["blocking_codes"] != [C.BLOCK_SILENCE]:
        return fail(f"silent codes {silent['blocking_codes']}")
    if reasoned["blocking_codes"] != [C.BLOCK_REASONED]:
        return fail(f"reasoned codes {reasoned['blocking_codes']}")
    if token["blocking_codes"] != [C.BLOCK_TOKEN]:
        return fail(f"token codes {token['blocking_codes']}")
    if silent["stopping_ok"] or reasoned["stopping_ok"] or token["stopping_ok"]:
        return fail("a naive-0.95 defective fixture was allowed to stop")
    if not good["stopping_ok"] or good["blocking_codes"] != []:
        return fail("known-good unanimous did not pass")
    if good["naive_fraction"] != "20/20":
        return fail("unanimous naive not 20/20")

    # Distinguishability of the two required fixtures is the class pair,
    # not merely stopping_ok (both fail). Token is a third quality.
    class_triple = (
        (silent["n_silent"], silent["n_reasoned_dissent"], silent["n_token_dissent"]),
        (
            reasoned["n_silent"],
            reasoned["n_reasoned_dissent"],
            reasoned["n_token_dissent"],
        ),
        (token["n_silent"], token["n_reasoned_dissent"], token["n_token_dissent"]),
    )
    if len(set(class_triple)) != 3:
        return fail(f"quality vectors not unique: {class_triple}")

    print("NEGATIVE_CONTROL_VERBATIM=" + C.NEGATIVE_CONTROL_VERBATIM)

    if not OUT.is_file():
        return fail(f"artifact missing {OUT}")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0069" not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel absent from artifact")
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("catalog output_schema shim missing")
    if not S.catalog_shim_present():
        return fail("catalog output_schema is not the council-design-note $ref shim")
    try:
        S.validate_note(doc)
    except Exception as exc:  # ValidationError or schema compile failure
        return fail(f"local schema: {type(exc).__name__}: {exc}")
    garbage_rejected = S.garbage_rejected()
    if garbage_rejected != 3:
        return fail(f"schema vacuous garbage_rejected={garbage_rejected}")

    recorded = {
        row["id"]: row
        for row in (doc.get("fixture_results") or [])
        if isinstance(row, dict)
    }
    for key, live in (
        ("naive-095-silent", silent),
        ("naive-095-reasoned-dissent", reasoned),
        ("known-good-unanimous", good),
    ):
        rec = recorded.get(key) or {}
        ok, why = C.counts_match(live, rec)
        if not ok:
            return fail(f"artifact stale vs live tally {key}: {why}")

    fired_on_bad = (not silent["stopping_ok"]) and (not reasoned["stopping_ok"])
    silent_on_good = good["stopping_ok"] is True
    print(f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}")
    print("SUCCESS:CNL-0069-probe1 naive-0.95 fixtures distinguished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
