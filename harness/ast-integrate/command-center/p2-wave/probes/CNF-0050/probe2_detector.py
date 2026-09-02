#!/usr/bin/env python3
"""Probe 2: detector controls on known-good / unexecuted / wrong-recipe / mention / ambiguous."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import run_all_controls  # noqa: E402
from paths import OUT_REL, REPO, UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file():
        return fail("artifact missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    scratch = Path(tempfile.mkdtemp(prefix="cnf0050-p2-"))
    controls = run_all_controls(scratch)
    printable = [
        {
            "id": c["id"],
            "pass": c.get("pass"),
            "fired_on_bad": c.get("fired_on_bad"),
            "silent_on_good": c.get("silent_on_good"),
        }
        for c in controls
    ]
    print(json.dumps(printable, sort_keys=True))

    failed = [c["id"] for c in controls if not c.get("pass")]
    if failed:
        print(json.dumps(controls, default=str)[:4000])
        return fail(f"controls failed: {failed}")

    unexec = next(c for c in controls if c["id"] == "unexecuted-refused")
    good = next(c for c in controls if c["id"] == "known-good-records")
    if not unexec.get("fired_on_bad"):
        return fail("unexecuted mutant did not fire")
    if not unexec.get("silent_on_good"):
        return fail("completeness not silent on known-good")
    if unexec.get("fired_on_bad") == good.get("silent_on_good") is True:
        pass
    else:
        return fail("both-states control did not discriminate")

    nc = doc.get("negative_controls") or []

    def _fired(row: dict) -> bool:
        if "fired_on_bad_state" in row:
            return bool(row.get("fired_on_bad_state"))
        return bool(row.get("fired_on_bad"))

    if not any(x.get("id") == "unexecuted-refused" and _fired(x) for x in nc):
        return fail("artifact missing unexecuted negative control")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "control-unexecuted-refused",
        "control-wrong-recipe",
        "control-use-vs-mention",
        "control-ambiguous",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    print(
        "unexecuted_fired=True known_good_silent=True "
        "wrong_recipe_filed=True mention_silent=True ambiguous_not_run=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 detector controls fire in both states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
