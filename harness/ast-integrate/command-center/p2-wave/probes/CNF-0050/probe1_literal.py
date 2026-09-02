#!/usr/bin/env python3
"""Probe 1: re-run the live guide literally; every step must still be recorded."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import canonical_steps, completeness, measure_live  # noqa: E402
from paths import CATALOG_SENTINEL, OUT_REL, REPO, SCHEMA_REL, UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id mismatch")
    if doc.get("unexecuted_count") != 0:
        return fail(f"unexecuted_count={doc.get('unexecuted_count')}")

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    sandbox = Path(tempfile.mkdtemp(prefix="cnf0050-p1-")) / "sandbox"
    sandbox.mkdir(parents=True)
    live = measure_live(sandbox)
    ok, problems = completeness(live["steps"])
    if not ok:
        return fail(f"live completeness {problems}")

    recorded = canonical_steps(doc.get("steps") or [])
    fresh = canonical_steps(live["steps"])
    if recorded != fresh:
        print(json.dumps({"recorded": recorded, "fresh": fresh}, default=str)[:4000])
        return fail("canonical step table drifted from live re-run")

    if live["guide_followable"] != doc.get("guide_followable"):
        return fail("guide_followable drifted")

    if len(doc.get("reviewers") or []) < 2:
        return fail("need two reviewers")
    for rev in doc["reviewers"]:
        if rev.get("independent") is not True:
            return fail("reviewer not independent")
        if rev.get("saw_other_verdict_before_filing") is not False:
            return fail("reviewer saw the other verdict")

    missing_named = [
        s
        for s in live["steps"]
        if s.get("command", "").startswith("test -f command-center/")
        and s.get("exit_code") != 0
    ]
    if not missing_named and live["guide_followable"] is not True:
        # If files appeared, followable may change; still require recording.
        pass
    if missing_named and doc.get("guide_followable") is True:
        return fail("guide_followable true while named inputs fail test -f")

    out = {
        "probe": "probe1-literal-rerun",
        "unit_id": UNIT,
        "steps": len(fresh),
        "unexecuted": live["unexecuted_count"],
        "guide_followable": live["guide_followable"],
        "canonical_match": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"steps={len(fresh)} unexecuted={live['unexecuted_count']} "
        f"followable={live['guide_followable']} match=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 literal re-run matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
