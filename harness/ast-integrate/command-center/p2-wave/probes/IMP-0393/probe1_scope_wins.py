#!/usr/bin/env python3
"""Probe 1: scoped vs unscoped most-specific-wins + unique-name negative control.

Catalog tests_required:
  fixture with a scoped and an unscoped variant of one name; assert most-specific
  wins from inside the scoped directory and unscoped wins outside it. Negative
  control: a name with no duplicate must not enter the resolution path at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from conflict_resolve import (  # noqa: E402
    PASSTHROUGH_RULE,
    SCOPE_RULE,
    UNSCOPED_OUTSIDE_RULE,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0393-probe1 {msg}")
    return 1


def winner_id(report: dict, name: str) -> str | None:
    row = report["winners_by_name"][name]
    w = row.get("winner") or {}
    return w.get("capability_id")


def main() -> int:
    idx = S.index()
    names = {r["name"] for r in idx["records"]}
    if "deploy" not in names or "unique-only" not in names:
        return fail("fixture missing deploy or unique-only")

    inside_web = S.resolve_at(S.CWD_WEB_SRC)
    inside_app = S.resolve_at(S.CWD_WEB_APP_SRC)
    outside = S.resolve_at(S.CWD_OTHER)

    dep_web = inside_web["winners_by_name"]["deploy"]
    dep_app = inside_app["winners_by_name"]["deploy"]
    dep_out = outside["winners_by_name"]["deploy"]

    if not dep_web["entered_resolution"] or not dep_out["entered_resolution"]:
        return fail("deploy must enter resolution (it is duplicated)")
    if dep_web["rule"] != SCOPE_RULE:
        return fail(f"inside web rule={dep_web['rule']} want={SCOPE_RULE}")
    if winner_id(inside_web, "deploy") != "cap.deploy.web":
        return fail(
            f"inside web winner={winner_id(inside_web, 'deploy')} want=cap.deploy.web"
        )
    if dep_app["rule"] != SCOPE_RULE:
        return fail(f"inside app rule={dep_app['rule']} want={SCOPE_RULE}")
    if winner_id(inside_app, "deploy") != "cap.deploy.web-app":
        return fail(
            f"inside app winner={winner_id(inside_app, 'deploy')} want=cap.deploy.web-app"
        )
    if dep_out["rule"] != UNSCOPED_OUTSIDE_RULE:
        return fail(f"outside rule={dep_out['rule']} want={UNSCOPED_OUTSIDE_RULE}")
    if winner_id(outside, "deploy") != "cap.deploy.unscoped":
        return fail(
            f"outside winner={winner_id(outside, 'deploy')} want=cap.deploy.unscoped"
        )

    uniq = outside["winners_by_name"]["unique-only"]
    if uniq["entered_resolution"]:
        return fail("unique-only entered the resolution path")
    if uniq["rule"] != PASSTHROUGH_RULE:
        return fail(f"unique-only rule={uniq['rule']} want={PASSTHROUGH_RULE}")
    if "unique-only" in inside_web["duplicate_names"]:
        return fail("unique-only listed as a duplicate")
    if "unique-only" not in inside_web["passthrough_names"]:
        return fail("unique-only missing from passthrough")
    if winner_id(inside_web, "unique-only") != "cap.unique-only":
        return fail("unique-only winner drifted")

    # Negative control both-states: forcing unique-only through a duplicated
    # pool would enter resolution. Detector must stay silent on the real
    # singleton and fire on a synthetic duplicate.
    synthetic = list(idx["records"])
    clone = dict(next(r for r in synthetic if r["name"] == "unique-only"))
    clone["capability_id"] = "cap.unique-only.mutant"
    clone["path"] = "trees/repo-skills/deploy/SKILL.md"
    synthetic.append(clone)
    from conflict_resolve import resolve_name  # noqa: E402

    mutant = resolve_name(
        "unique-only",
        [r for r in synthetic if r["name"] == "unique-only"],
        S.CWD_OTHER,
        idx["root"],
    )
    if not mutant["entered_resolution"]:
        return fail("mutant duplicate unique-only did not enter resolution")

    summary = {
        "probe": "probe1-scope-wins",
        "inside_web_winner": winner_id(inside_web, "deploy"),
        "inside_app_winner": winner_id(inside_app, "deploy"),
        "outside_winner": winner_id(outside, "deploy"),
        "unique_entered_resolution": uniq["entered_resolution"],
        "mutant_entered_resolution": mutant["entered_resolution"],
        "pass": True,
        "unit_id": "IMP-0393",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "inside_web="
        + str(winner_id(inside_web, "deploy"))
        + " inside_app="
        + str(winner_id(inside_app, "deploy"))
        + " outside="
        + str(winner_id(outside, "deploy"))
        + " unique_entered="
        + str(uniq["entered_resolution"])
        + " mutant_entered="
        + str(mutant["entered_resolution"])
    )
    print("SUCCESS:IMP-0393-probe1 most-specific-scope-wins and unique passthrough")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
