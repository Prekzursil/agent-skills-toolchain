"""IMP-0071: channel pins and PR-ONLY release mode (stdlib runner)."""
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from channels import run_pin_matrix  # noqa: E402


def test_pin_stable():
    m = run_pin_matrix()
    row = [r for r in m["results"] if r["id"] == "pin-stable"][0]
    assert row["ok"] and row["got"] is True


def test_pin_beta():
    m = run_pin_matrix()
    row = [r for r in m["results"] if r["id"] == "pin-beta"][0]
    assert row["ok"] and row["got"] is True


def test_cross_channel_refusal():
    m = run_pin_matrix()
    row = [r for r in m["results"] if r["id"] == "cross-channel-refuse"][0]
    assert row["ok"] and row["got"] is False


def test_pin_does_not_mutate_index():
    from index_model import fixture_index, index_sha256

    idx = fixture_index()
    before = index_sha256(idx)
    assert before == index_sha256(idx)


def test_ten_case_matrix():
    m = run_pin_matrix()
    assert m["cases"] == 10 and m["passed"] == 10 and m["pass"]


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, exc)
    print("SUCCESS:test_channels %d passed" % (0 if failed else 5) if not failed else "FAILED:test_channels")
    sys.exit(1 if failed else 0)
