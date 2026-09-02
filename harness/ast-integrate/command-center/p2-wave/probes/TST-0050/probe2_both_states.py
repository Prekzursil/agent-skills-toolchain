#!/usr/bin/env python3
"""Probe 2: both-states — conforming silent, each contract rule fires on bad."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checker import leak_needles_in  # noqa: E402
from contract import RULES  # noqa: E402
from paths import CATALOG_SENTINEL, OUT_REL, REPO, UNIT  # noqa: E402
from suite import both_states, decision_ids, load_json, public_control_rows  # noqa: E402

FIXTURES = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file():
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    leaks = leak_needles_in(text)
    if leaks:
        return fail(f"artifact leaked sensitive canaries {leaks}")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    log_ids = decision_ids(load_json(FIXTURES / "decision_log.json"))
    controls = both_states(log_ids)
    printable = public_control_rows(controls)
    print(json.dumps(printable, sort_keys=True))
    if not controls.get("pass"):
        print(json.dumps(controls, default=str)[:4000])
        return fail("both-states did not discriminate")

    failed = [r["id"] for r in controls["rows"] if not r.get("pass")]
    if failed:
        return fail(f"controls failed: {failed}")

    covered = {r["id"] for r in controls["rows"]}
    missing = [r for r in RULES if r not in covered]
    if missing:
        return fail(f"missing negative case for rules {missing}")

    nc = doc.get("negative_controls") or []
    nc_ids = {x.get("id") for x in nc if isinstance(x, dict)}
    for rule in RULES:
        row = next((x for x in nc if x.get("id") == rule), None)
        if not row:
            return fail(f"artifact missing negative control {rule}")
        if not row.get("fired_on_bad"):
            return fail(f"artifact {rule} did not fire on bad")
        if not row.get("silent_on_good"):
            return fail(f"artifact {rule} not silent on good")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("probe1-live-capture", "probe2-both-states", "control-declared-fields"):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    if not controls.get("checker_omits_sensitive_values"):
        return fail("checker printed a sensitive value")
    if "never-print-sensitive" not in nc_ids and not any(
        r.get("id") == "never-print-sensitive" for r in controls["rows"]
    ):
        return fail("never-print control missing")

    print(
        "conforming_silent=True extra_field_fired=True credential_fired=True "
        "path_fired=True disabled_fired=True no_print=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 both-states fire per contract rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
