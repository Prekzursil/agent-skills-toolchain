#!/usr/bin/env python3
"""Probe 2: load-semantics control on a scratch copy.

Direct measurement: read the turn-zero context bag (injected body bytes),
not a frontmatter classifier.

  1. Known always-on skill and the no-frontmatter rule must appear in the bag.
  2. The paths-scoped skill/rule must NOT appear in the bag (index only).
  3. Adding `paths: ["**/*"]` to the always-on skill DEMOTES it: body leaves
     the bag even though the glob matches everything.
  4. Touching src/app.py then injects the original lazy skill, and only then.
  5. An empty always-on set is a broken instrument, not evidence of lazy load.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import loader as L  # noqa: E402
from frontmatter import split_frontmatter  # noqa: E402

OUT = HERE / "probe2-load-semantics.raw.json"
SCHEMA = REPO / "command-center" / "phase4" / "contracts" / "ARC-0089.json"


def validate_trace(doc: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)


def demote_with_paths(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        raise SystemExit("FAILED:ARC-0089-probe2 always-on skill had no frontmatter")
    if "paths" in fm:
        raise SystemExit("FAILED:ARC-0089-probe2 control file already had paths")
    # Insert the scoping field into the existing fence. Presence, not glob
    # value, is the switch: **/* still demotes because turn zero has no touch.
    fence = "---\n"
    for k, v in fm.items():
        fence += f"{k}: {v}\n"
    fence += "paths:\n  - \"**/*\"\n---\n"
    skill_md.write_text(fence + "\n" + body.lstrip("\n"), encoding="utf-8", newline="\n")


def main() -> int:
    src = F.build_scratch()
    tmp = Path(tempfile.mkdtemp(prefix="arc-0089-scratch-"))
    try:
        dest = tmp / "tree"
        shutil.copytree(src, dest)
        t0 = L.load_turn_zero(dest)
        rec0 = L.as_record(t0)
        validate_trace(rec0)

        always_on_in_bag = t0.body_contains("always-on", "TURN0-BODY:always-on")
        bare_in_bag = t0.body_contains("rules.common.no-frontmatter.md", "TURN0-BODY:bare-rule")
        lazy_out = "LAZY-BODY:lazy-scoped" not in t0.injected_bodies.get("lazy-scoped", "")
        path_rule_out = "LAZY-BODY:path-rule" not in "".join(t0.injected_bodies.values())
        lazy_indexed = "lazy-scoped" in t0.index_cards
        instrument_names_always_on = bool(t0.always_on_ids)

        demote_with_paths(dest / "always-on" / "SKILL.md")
        t1 = L.load_turn_zero(dest)
        rec1 = L.as_record(t1)
        validate_trace(rec1)
        demoted = (
            "always-on" not in t1.injected_bodies
            and "always-on" in t1.lazy_ids
            and "always-on" in t1.index_cards
            and not t1.body_contains("always-on", "TURN0-BODY:always-on")
        )
        # The glob **/* would match any touch, but turn zero still has none.
        still_out_without_touch = "always-on" not in t1.injected_bodies

        t2 = L.load_turn_zero(dest, touched_path="src/app.py")
        rec2 = L.as_record(t2)
        validate_trace(rec2)
        lazy_on_touch = t2.body_contains("lazy-scoped", "LAZY-BODY:lazy-scoped")
        demoted_on_star_touch = t2.body_contains("always-on", "TURN0-BODY:always-on")
        path_rule_still_out = "LAZY-BODY:path-rule" not in "".join(
            t2.injected_bodies.values()
        )

        t3 = L.load_turn_zero(dest, touched_path="tests/test_x.py")
        path_rule_on_tests = "LAZY-BODY:path-rule" in "".join(t3.injected_bodies.values())
        lazy_not_on_tests = "LAZY-BODY:lazy-scoped" not in t3.injected_bodies.get(
            "lazy-scoped", ""
        )

        payload = {
            "instrument": L.INSTRUMENT,
            "measurement_command": L.MEASUREMENT_COMMAND,
            "turn0": rec0,
            "after_demote": rec1,
            "after_touch_src": rec2,
            "always_on_in_bag": always_on_in_bag,
            "bare_rule_in_bag": bare_in_bag,
            "lazy_body_absent_at_t0": lazy_out,
            "path_rule_absent_at_t0": path_rule_out,
            "lazy_indexed_at_t0": lazy_indexed,
            "instrument_named_always_on": instrument_names_always_on,
            "demoted_by_paths_star": demoted,
            "star_glob_still_lazy_at_t0": still_out_without_touch,
            "lazy_injected_on_src_touch": lazy_on_touch,
            "demoted_star_injects_on_any_touch": demoted_on_star_touch,
            "path_rule_absent_on_src_touch": path_rule_still_out,
            "path_rule_injected_on_tests_touch": path_rule_on_tests,
            "lazy_absent_on_tests_touch": lazy_not_on_tests,
        }
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(
            "instrument="
            + L.INSTRUMENT
            + " t0.injected="
            + ",".join(t0.injected_ids())
            + " t0.lazy="
            + ",".join(sorted(t0.lazy_ids))
            + " always_on_in_bag="
            + str(always_on_in_bag)
            + " bare_rule_in_bag="
            + str(bare_in_bag)
            + " lazy_out="
            + str(lazy_out)
            + " demoted="
            + str(demoted)
            + " lazy_on_src_touch="
            + str(lazy_on_touch)
            + " path_rule_on_tests="
            + str(path_rule_on_tests)
        )
        ok = (
            always_on_in_bag
            and bare_in_bag
            and lazy_out
            and path_rule_out
            and lazy_indexed
            and instrument_names_always_on
            and demoted
            and still_out_without_touch
            and lazy_on_touch
            and demoted_on_star_touch
            and path_rule_still_out
            and path_rule_on_tests
            and lazy_not_on_tests
        )
        if not ok:
            print("FAILED:ARC-0089-probe2 load-semantics control")
            return 1
        print("SUCCESS:ARC-0089-probe2 load-semantics demotion measured")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
