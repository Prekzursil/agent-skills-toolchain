"""IMP-0099: advisory record + affected-version-range model (stdlib runner)."""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
from marketplace.advisory import OpenEndedUndisclosedError, evaluate_installed, from_record, is_affected  # noqa: E402
from marketplace.version import satisfies  # noqa: E402

FIXTURE = W / "tools" / "marketplace" / "fixtures" / "imp0099_matrix.json"


def test_matrix_matches_expected():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    adv = from_record(fx["advisory"])
    for case in fx["cases"]:
        assert is_affected(adv, case["version"]) is bool(case["expected_affected"]), case["id"]


def test_comparator_parity():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in fx["cases"]:
        assert satisfies(case["version"], fx["imp0070_range"]) is bool(case["expected_affected"]), case["id"]


def test_negative_control_scoping():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    adv = from_record(fx["advisory"])
    neg = fx["negative_control"]
    assert evaluate_installed(fx["package"], neg["affected_package_version"], [adv]).affected
    assert not evaluate_installed(fx["package"], neg["unaffected_sibling_version"], [adv]).affected
    assert not evaluate_installed(fx["sibling_package"], neg["unaffected_sibling_package_version"], [adv]).affected


def test_open_ended_requires_disclosure():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    disclosed = fx["open_ended_advisory"]
    undisclosed = {k: v for k, v in disclosed.items() if k != "unbounded_future_disclosed"}
    try:
        from_record(undisclosed)
    except OpenEndedUndisclosedError:
        pass
    else:
        raise AssertionError("undisclosed open range accepted")


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
    print("SUCCESS:test_advisory_ranges" if not failed else "FAILED:test_advisory_ranges")
    sys.exit(1 if failed else 0)
