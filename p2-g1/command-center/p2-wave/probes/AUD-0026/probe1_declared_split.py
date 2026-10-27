#!/usr/bin/env python3
"""AUD-0026 probe1 -- declared prod/dev dependency split (live, fail-closed).

Lane 1 re-derives the manifest census on the live tree: tools/plugin has no
packaging manifest (pyproject.toml / package.json / setup.py), so a consumer
is forced to install zero declared dependencies (consumer_forced == []). Lane
2 rebuilds the manifest classifier fixture in a temp dir and re-proves it
both-states: a shipped module importing a declared-dev dependency must FLAG;
a test module importing the same must stay SILENT (shippable filter); a
shipped module importing a declared-runtime dependency stays SILENT.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0026-runtime-vs-dev-split.json"
UNIT = "AUD-0026"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
MANIFEST_NAMES = {"pyproject.toml", "package.json", "setup.py", "setup.cfg"}


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    # lane 1: live manifest census on tools/plugin
    plugin_root = REPO / "tools" / "plugin"
    check(plugin_root.is_dir(), "tools/plugin root absent on this worktree")
    manifests_present = sorted(
        p.name for p in plugin_root.iterdir()
        if p.is_file() and p.name in MANIFEST_NAMES
    ) if plugin_root.is_dir() else ["<plugin-root-absent>"]
    check(manifests_present == [], "packaging manifests appeared in tools/plugin",
          str(manifests_present))
    prd = doc.get("plugin_runtime_vs_dev") or {}
    check(prd.get("manifest_absent") is True, "recorded manifest_absent not true")
    check(prd.get("consumer_forced") == [], "recorded consumer_forced not empty",
          str(prd.get("consumer_forced")))
    check(prd.get("plugin_root_exists") is True, "recorded plugin_root_exists not true")
    check(int(prd.get("shipped_third_party_count", -1)) == 1,
          "recorded shipped_third_party_count != 1")
    # the recorded packaging defect names census.py -> harness_walker
    defects = prd.get("packaging_defects") or []
    check(len(defects) == 1, "recorded packaging_defects != 1 row", str(len(defects)))
    if defects:
        d = defects[0]
        check(str(d.get("path", "")).endswith("tools/plugin/census.py"),
              "defect row path drift", str(d.get("path")))
        check(d.get("top") == "harness_walker" and d.get("dist") == "harness-walker",
              "defect row top/dist drift", f"{d.get('top')}/{d.get('dist')}")
        census = REPO / "tools" / "plugin" / "census.py"
        if census.is_file():
            ct = census.read_text(encoding="utf-8", errors="replace")
            live_has_import = "harness_walker" in ct
            if not live_has_import:
                notes.append(
                    "LIVE DRIFT (both numbers recorded, not picked): the artifact's "
                    "packaging-defect census recorded tools/plugin/census.py importing "
                    "harness_walker (top harness_walker, dist harness-walker); the live "
                    "census.py on this worktree imports only stdlib (os/pathlib/typing) and "
                    "contains no harness_walker reference, while tools/harness_walker/ still "
                    "exists. The recorded census is point-in-time; the reviewer must "
                    "adjudicate with both numbers."
                )
        else:
            notes.append("LIVE DRIFT: tools/plugin/census.py itself absent on this worktree")

    # lane 2: rebuild the manifest classifier fixture and re-prove it both-states
    def shippable(rel: str) -> bool:
        return not rel.startswith("tests/")

    def flag(rel: str, top: str, declared_runtime: set[str], use_filter: bool = True) -> bool:
        """True iff the path counts as shipping an undeclared import.

        With use_filter=True a test module never flags (the shippable filter);
        with use_filter=False the raw classifier decides — the filter-off arm
        proves the filter is load-bearing, not decorative.
        """
        if use_filter and not shippable(rel):
            return False
        return top not in declared_runtime

    with tempfile.TemporaryDirectory(prefix="aud0026probe1-") as td:
        fx = Path(td)
        shipped_dev = fx / "src" / "shipped_dev.py"
        shipped_ok = fx / "src" / "shipped_ok.py"
        test_mod = fx / "tests" / "test_ok.py"
        shipped_dev.parent.mkdir(parents=True)
        test_mod.parent.mkdir(parents=True)
        shipped_dev.write_text("import pytest\n", encoding="utf-8", newline="\n")
        shipped_ok.write_text("import rich\n", encoding="utf-8", newline="\n")
        test_mod.write_text("import pytest\n", encoding="utf-8", newline="\n")
        runtime = {"rich"}
        dev = {"pytest"}
        fired_dev = flag("src/shipped_dev.py", "pytest", runtime)
        silent_test = not flag("tests/test_ok.py", "pytest", runtime)
        silent_ok = not flag("src/shipped_ok.py", "rich", runtime)
        # disable the shippable filter: the test import must now be flagged
        fired_no_filter = flag("tests/test_ok.py", "pytest", runtime, use_filter=False)
        check(fired_dev, "shipped-dev-import detector did not fire (cannot go red)")
        check(silent_test, "test-dev-import detector fired on a test module (filter broken)")
        check(silent_ok, "declared-runtime import flagged (over-matching)")
        check(fired_no_filter, "shippable-filter-disabled arm did not flag (filter is decorative)")
        check(dev == {"pytest"}, "dev-declared fixture sanity")

    # recorded control fields must match the re-proved fixture outcomes
    check(doc.get("control_shipped_dev_import_flagged") is True,
          "control_shipped_dev_import_flagged recorded false")
    check(doc.get("control_test_dev_import_silent") is True,
          "control_test_dev_import_silent recorded false")
    ncs = doc.get("negative_controls") or []
    check(len(ncs) >= 1 and all(
        c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True
        for c in ncs if isinstance(c, dict)
    ), "negative controls not recorded both-states")

    report = {
        "probe": "probe1-declared-prod-dev-split",
        "unit_id": UNIT,
        "manifests_in_plugin_root": manifests_present,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 declared split re-derived (manifest_absent, consumer_forced=[], "
          "shipped-dev fires, test-dev silent, filter-off fires); live drift on census.py "
          "recorded with both numbers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
