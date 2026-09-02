#!/usr/bin/env python3
"""Named probe 1: ignored-argument fixture + both-states unanswered check.

Signal 1 is the unanswered-obligation detector on synthesized status labels.
The planted-bad (ignored) fixture must FIRE; the known-good fixture must be
SILENT. The ignored obligation must remain a graph node after synthesis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0048-response-obligations-and-rebuttal-depth.md"
FIX = HERE / "fixtures"


def load_fix(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def run_named(name: str, *, drop_ignored: bool = False) -> dict:
    doc = load_fix(name)
    return E.apply_turns(doc["turns"], int(doc["rebuttal_depth_budget"]), drop_ignored=drop_ignored)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 80:
        print("FAILED:CNL-0048-probe1 artifact missing")
        return 1
    art_text = ART.read_text(encoding="utf-8")
    try:
        art = json.loads(art_text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0048-probe1 artifact unparseable {exc}")
        return 1
    if art.get("unit_id") != "CNL-0048":
        print("FAILED:CNL-0048-probe1 unit_id", art.get("unit_id"))
        return 1
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0048-probe1 self-declared", art.get("state"))
        return 1
    if "SUCCESS:CNL-0048" not in art_text:
        print("FAILED:CNL-0048-probe1 sentinel absent")
        return 1

    good = run_named("known_good")
    bad = run_named("ignored_argument")
    mutant = run_named("ignored_argument", drop_ignored=True)
    depth = run_named("depth_cut")

    good_line = E.verbatim_check("known_good", good)
    bad_line = E.verbatim_check("ignored_argument", bad)
    mutant_line = E.verbatim_check("silent_drop_mutant", mutant)
    depth_line = E.verbatim_check("depth_cut", depth)
    print(good_line)
    print(bad_line)
    print(mutant_line)
    print(depth_line)

    if good["unanswered_fires"]:
        print("FAILED:CNL-0048-probe1 known-good was not SILENT")
        return 1
    if not bad["unanswered_fires"]:
        print("FAILED:CNL-0048-probe1 ignored-argument did not FIRE")
        return 1
    if not bad["ignored_visible"]:
        print("FAILED:CNL-0048-probe1 ignored obligation dropped from graph")
        return 1
    if "obl:n0" not in bad["ignored_ids"]:
        print("FAILED:CNL-0048-probe1 expected obl:n0 ignored", bad["ignored_ids"])
        return 1
    if not any(
        n.get("id") == "obl:n0" and n.get("status") == "IGNORED"
        for n in bad["graph"]["nodes"]
    ):
        print("FAILED:CNL-0048-probe1 obl:n0 not on synthesized graph")
        return 1
    # Negative control: silent-drop mutant is the state the visibility check rejects.
    if mutant["unanswered_fires"]:
        print("FAILED:CNL-0048-probe1 drop-mutant still showed IGNORED (not a drop)")
        return 1
    if not mutant["silent_drop_fires"]:
        print("FAILED:CNL-0048-probe1 silent-drop detector did not fire on mutant")
        return 1
    if depth["unanswered_fires"]:
        print("FAILED:CNL-0048-probe1 depth-cut masqueraded as IGNORED")
        return 1
    if not any(c.get("status") == "CUT_BY_DEPTH" for c in depth["cuts"]) and not any(
        o.get("status") == "CUT_BY_DEPTH" for o in depth["obligations"]
    ):
        print("FAILED:CNL-0048-probe1 depth-cut produced no CUT_BY_DEPTH marker")
        return 1
    n2_accepted = "n2" in depth["nodes"]
    if n2_accepted:
        print("FAILED:CNL-0048-probe1 n2 at depth 2 accepted under budget 1")
        return 1

    print(
        "fired_on_bad=True silent_on_good=True "
        "ignored_visible=True silent_drop_detected=True depth_not_ignored=True"
    )
    print("SUCCESS:CNL-0048-probe1 both-states ignored-argument")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
