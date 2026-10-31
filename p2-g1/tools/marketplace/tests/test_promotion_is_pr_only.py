"""IMP-0071: promotion is a PR diff; direct writes refused (stdlib runner)."""
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from index_model import fixture_index, index_sha256  # noqa: E402
from promotion import DirectWritePromotionRefused, apply_promotion_to_index_file, promote_direct_write, promote_via_pr  # noqa: E402


def test_no_direct_index_write():
    promo = promote_via_pr(fixture_index(), package="echo", version="1.1.0-beta.1", from_channel="beta", to_channel="stable")
    assert promo.direct_index_writes == 0 and promo.pr_diff


def test_pr_diff_leaves_caller_index_untouched():
    idx = fixture_index()
    before = index_sha256(idx)
    promote_via_pr(idx, package="echo", version="1.1.0-beta.1", from_channel="beta", to_channel="stable")
    assert index_sha256(idx) == before


def test_apply_promotion_to_index_file_refused():
    promo = promote_via_pr(fixture_index(), package="echo", version="1.1.0-beta.1", from_channel="beta", to_channel="stable")
    try:
        apply_promotion_to_index_file(Path(W / "x-must-not-exist.json"), promo)
    except DirectWritePromotionRefused:
        return
    raise AssertionError("apply_promotion_to_index_file did not refuse")


def test_naive_in_place_write_would_change_hash():
    idx = fixture_index()
    before = index_sha256(idx)
    mutated = fixture_index()
    mutated["packages"]["echo"]["versions"]["1.1.0-beta.1"]["channel"] = "stable"
    assert index_sha256(mutated) != before


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
    print("SUCCESS:test_promotion_is_pr_only 4 passed" if not failed else "FAILED:test_promotion_is_pr_only")
    sys.exit(1 if failed else 0)
