"""The three catalog-required tests plus labelled precision/recall."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
import eval_kit  # noqa: E402
import kit  # noqa: E402

FENCED = HERE / "fixtures" / "fenced.md"
TYPED = HERE / "fixtures" / "typed_status.json"
KIT_DOC = HERE / "KIT.md"
UNIT_DESCRIPTION = (
    "Target: a reusable helper that answers 'is this token USED (a semantic "
    "role in a typed field) or MENTIONED (text inside a payload, a fenced "
    "block, a doc body)?' and a labelled fixture kit of adversarial cases. "
    "A file documenting a defect necessarily contains that defect's text — "
    "measured ~8 hits in one session, mostly inside the verification probes "
    "themselves."
)


def test_token_in_fenced_code_block_is_mention() -> None:
    text = FENCED.read_text(encoding="utf-8")
    occs = kit.classify_token(text, "FAILED")
    fenced = [o for o in occs if o.reason == "fenced-code-block"]
    if not fenced:
        raise AssertionError("no fenced FAILED span in fenced.md")
    if any(o.role != "MENTION" for o in fenced):
        raise AssertionError(f"fenced span not MENTION: {fenced}")
    if any(o.role == "USE" for o in occs):
        raise AssertionError(f"fenced.md produced USE: {occs}")


def test_token_in_typed_status_field_is_use() -> None:
    text = TYPED.read_text(encoding="utf-8")
    got = kit.roles(text, "FAILED")
    if got != ["USE"]:
        raise AssertionError(f"typed status expected [USE], got {got}")
    occs = kit.classify_token(text, "FAILED")
    if occs[0].reason != "typed-field:status":
        raise AssertionError(f"reason {occs[0].reason}")


def test_the_kit_does_not_flag_its_own_documentation() -> None:
    doc = KIT_DOC.read_text(encoding="utf-8")
    for token in ("FAILED", "USED", "MENTIONED"):
        occs = kit.classify_token(doc, token)
        if not occs:
            raise AssertionError(f"expected {token} in KIT.md")
        bad = [o for o in occs if o.role == "USE"]
        if bad:
            raise AssertionError(f"KIT.md flagged {token} as USE: {bad}")
    for token in ("USED", "MENTIONED"):
        roles = kit.roles(UNIT_DESCRIPTION, token)
        if roles != ["MENTION"]:
            raise AssertionError(
                f"unit description {token} expected [MENTION], got {roles}"
            )


def test_labelled_precision_recall() -> dict:
    report = eval_kit.score()
    if not report["all_exact"]:
        raise AssertionError(f"labelled mismatches {report['mismatches']}")
    if report["precision_use"] != 1.0 or report["recall_use"] != 1.0:
        raise AssertionError(
            f"precision={report['precision_use']} recall={report['recall_use']}"
        )
    return report


def run_all() -> dict:
    test_token_in_fenced_code_block_is_mention()
    test_token_in_typed_status_field_is_use()
    test_the_kit_does_not_flag_its_own_documentation()
    labelled = test_labelled_precision_recall()
    return labelled
