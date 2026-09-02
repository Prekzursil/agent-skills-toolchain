#!/usr/bin/env python3
"""Probe 2: in-place vs clean classification, cache control, falsify headline.

Does not call engine.run_controls / detector status aggregation. Rebuilds the
env-only and docs-defect trees, plants a cache, rejects schema garbage, and
tries to falsify the clone-impossible headline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

UID = "AUD-0091"
ART = REPO / "command-center/audit/AUD-0091-clean-room-clone-baseline.json"
OUT = HERE / "probe2-inplace-compare-and-cache.raw.json"
SENTINEL = "SUCCESS:AUD-0091"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0091-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    rpt = doc.get("report") or {}
    if rpt.get("kind") != "audit-detector-control":
        return fail("report.kind is not audit-detector-control")

    env_tree = E.FIXTURES / "env_inplace"
    defect_tree = E.FIXTURES / "docs_defect"
    good_tree = E.FIXTURES / "good"

    env_clean = E.run_documented_tree(
        env_tree, clone_mode="copy", committed_only=["README.md"]
    )
    env_inplace = E.run_documented_tree(env_tree, clone_mode="inplace")
    defect_clean = E.run_documented_tree(defect_tree, clone_mode="copy")
    defect_inplace = E.run_documented_tree(defect_tree, clone_mode="inplace")
    cache_dirty = E.run_documented_tree(
        good_tree, clone_mode="copy", plant_package_cache=True
    )
    good_clean = E.run_documented_tree(good_tree, clone_mode="copy")

    env_class = E.classify(env_clean, env_inplace)
    defect_class = E.classify(defect_clean, defect_inplace)
    if env_class != "environment-only":
        return fail(f"env-only classified {env_class}")
    if env_inplace.get("all_ok") is not True:
        return fail("in-place env fixture should pass")
    if (env_clean.get("first_fail") or {}).get("exit_code") != 3:
        return fail(f"clean env fixture first_fail={env_clean.get('first_fail')}")
    if defect_class != "documentation-defect":
        return fail(f"docs defect classified {defect_class}")
    if (defect_clean.get("first_fail") or {}).get("exit_code") != 9:
        return fail(f"docs defect clean rc={(defect_clean.get('first_fail') or {})}")
    if (defect_inplace.get("first_fail") or {}).get("exit_code") != 9:
        return fail("docs defect in-place rc mismatch")
    if cache_dirty.get("skipped_for_dirty_cache") is not True:
        return fail("planted cache did not fire")
    if good_clean.get("cache", {}).get("ok") is not True:
        return fail("good fixture cache not free")
    if cache_dirty.get("first_fail", {}).get("exit_code") != 4:
        return fail("dirty cache first_fail was not the cache assertion")

    live_errors = SC.error_list(doc)
    if live_errors:
        return fail(f"artifact schema errors: {live_errors[:4]}")
    garbage_counts = SC.garbage_error_counts()
    if not all(c > 0 for c in garbage_counts):
        return fail(f"schema accepted garbage counts={garbage_counts}")

    falsify = E.falsify_headline()
    if falsify.get("verdict") != "STANDS":
        return fail(f"headline unexpectedly refuted: {falsify}")
    if falsify.get("git_dir_present") or falsify.get("inside_work_tree"):
        return fail("falsify found a git repository")
    if "README.md" not in (falsify.get("root_readme_glob") or []):
        return fail(f"expected root README.md: {falsify.get('root_readme_glob')}")
    named = falsify.get("named_present") or []
    if "README.md" not in named or "command-center/RUNBOOK.md" not in named:
        return fail(f"expected catalog-named docs: {named}")
    alt = falsify.get("alternate_doc") or {}
    if not alt.get("present") or not alt.get("commands"):
        return fail("expected docs/layout-migration.md as out-of-scope alternate")
    if alt.get("in_catalog_named_sources"):
        return fail("layout-migration must not be treated as README/RUNBOOK")

    art_env = (rpt.get("fixture_controls") or {}).get("env_only") or {}
    art_def = (rpt.get("fixture_controls") or {}).get("docs_defect") or {}
    if art_env.get("classification") != "environment-only":
        return fail("artifact env_only classification drift")
    if art_def.get("classification") != "documentation-defect":
        return fail("artifact docs_defect classification drift")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if (tests.get("AUD0091-inplace-vs-clean-and-cache") or {}).get("result") != "PASS":
        return fail("artifact test AUD0091-inplace-vs-clean-and-cache not PASS")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("artifact reviewer not PASS/independent")
    if rpt.get("control_executed") is not True:
        return fail("artifact report.control_executed is not true")

    raw = {
        "probe": "probe2-inplace-compare-and-cache",
        "unit_id": UID,
        "pass": True,
        "env_class": env_class,
        "defect_class": defect_class,
        "cache_fired": True,
        "schema_live_errors": 0,
        "schema_garbage_errors": sum(garbage_counts),
        "headline_verdict": falsify["verdict"],
        "alternate_doc_commands": alt.get("commands"),
        "named_present": named,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(raw, indent=1, sort_keys=True))
    print(
        f"env={env_class} defect={defect_class} cache_fired=True "
        f"garbage_errors={sum(garbage_counts)} falsify={falsify['verdict']}"
    )
    print(
        "SUCCESS:AUD-0091-probe2 env-only vs docs-defect distinguished; "
        "planted cache fires; headline stands"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
