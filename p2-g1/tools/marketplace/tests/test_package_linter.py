"""IMP-0113: linter composition == union of six standalone checks (stdlib)."""
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
from marketplace.checks import RULE_IDS, SUBCHECKS  # noqa: E402
from marketplace.package_linter import composition_sets, lint_package  # noqa: E402

BAD = W / "tools" / "marketplace" / "fixtures" / "known-bad"
GOOD = W / "tools" / "marketplace" / "fixtures" / "known-good"


def test_union_of_subchecks_equals_composer():
    ids = set(lint_package(BAD)["rule_ids"])
    union = set()
    for rid in RULE_IDS:
        for row in SUBCHECKS[rid](BAD):
            union.add(str(row.get("rule") or rid))
    assert ids == union == set(RULE_IDS)


def test_known_good_zero_findings():
    rep = lint_package(GOOD)
    assert rep["ok"] and not rep["findings"]


def test_disabling_secret_gate_leaves_exactly_that_gap():
    full = set(composition_sets(BAD)["rules"])
    reduced = set(composition_sets(BAD, enabled=[r for r in RULE_IDS if r != "secret-gate"])["rules"])
    assert full - reduced == {"secret-gate"}


def test_secret_report_prefix_only():
    rows = [f["detail"] for f in lint_package(BAD)["findings"] if f["rule"] == "secret-gate"]
    assert rows and all("body withheld" in d for d in rows)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS:" + name)
            except Exception as exc:
                failed += 1
                print("FAIL:" + name + " " + str(exc))
    print("SUCCESS:test_package_linter" if not failed else "FAILED:test_package_linter")
    sys.exit(1 if failed else 0)
