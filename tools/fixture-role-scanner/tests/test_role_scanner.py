"""Tests for the role-based fixture/content scanners (TST-0341)."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "hooks" / "_shared"))

from use_vs_mention import Context  # noqa: E402

from role_scanner import (  # noqa: E402
    evaluate_corpus_row,
    load_corpus,
    measure_all,
    measure_kind,
    scan_raw,
    scan_role,
    self_reference_silent,
)


def test_historical_false_positive_corpus_zero_flags_after_rebuild():
    report = measure_all()
    assert report["role_fp_total"] == 0, report
    assert report["ok"] is True


def test_true_positive_corpus_every_real_instance_still_flagged():
    report = measure_all()
    assert report["role_tp_missed"] == 0, report
    for kind, row in report["scanners"].items():
        if row["tp_corpus_size"] == 0:
            continue
        assert row["role_tp_complete"], (kind, row)


def test_raw_baseline_still_flags_false_positives():
    """Both numbers mandatory: raw must still be noisy so the rebuild is load-bearing."""
    report = measure_all()
    assert report["raw_fp_total"] > 0, "raw baseline went silent — control is vacuous"


def test_each_rebuilt_scanner_reports_fp_and_tp():
    corpus = load_corpus()
    kinds = sorted({r["kind"] for r in corpus})
    for kind in kinds:
        m = measure_kind(kind, corpus)
        assert "role_fp_flags" in m and "role_tp_flags" in m
        assert m["role_fp_flags"] == 0
        if m["tp_corpus_size"]:
            assert m["role_tp_flags"] == m["tp_corpus_size"]


def test_self_reference_receipt_like_document_not_flagged():
    doc = (
        "Historical false positives where payload text was matched instead of the verb:\n"
        "CMD-FP-writebody quoted `git push --force`; MRK-FP-mdprose named a placeholder;\n"
        "RES-FP-fieldname held `user_cancelled_or_timedout`; SEC-FP-faketoken held a ghp_ FAKE;\n"
        "STUB-FP-negated-absence asserted zero TODO/FIXME exist.\n"
    )
    result = self_reference_silent(doc)
    assert result["silent"] is True, result


def test_self_reference_live_receipt_patterns_not_flagged():
    """Catalog: own receipt contains forbidden patterns as examples and must stay silent.

    Reproduction of TST-0341 adversarial FAIL: unquoted snake field name + FAILED:UNIT
    sentinel vocabulary on the live receipt fired result:reported-value.
    """
    doc = (
        "role scanners; user_cancelled_or_timedout / ghp_ FAKE examples stay silent.\n"
        '{"sentinel": "FAILED:TST-0341 blocked-on-independent-review; role_fp=0"}\n'
    )
    result = self_reference_silent(doc)
    assert result["silent"] is True, result
    # Also exercise against the real receipt bytes when present.
    receipt = (
        Path(__file__).resolve().parents[3] / "command-center/receipts/TST-0341.json"
    )
    if receipt.is_file():
        live = self_reference_silent(receipt.read_text(encoding="utf-8"))
        assert live["silent"] is True, live


def test_scan_role_silent_on_write_body_command_mention():
    text = "git push --force origin main   # example shown in the docs"
    ctx = Context(tool_name="Write", file_path="docs/git.md", source="tool_input")
    assert scan_raw(text, kind="command")  # raw fires
    assert scan_role(text, kind="command", ctx=ctx) == []


def test_scan_role_fires_on_real_bash_force_push():
    text = "git push --force origin main"
    ctx = Context(tool_name="Bash", file_path="", source="tool_input")
    assert scan_role(text, kind="command", ctx=ctx)


def test_every_corpus_row_role_ok():
    fails = [
        evaluate_corpus_row(r)
        for r in load_corpus()
        if not evaluate_corpus_row(r).role_ok
    ]
    assert fails == []


def test_corpus_rows_are_covered():
    uncovered = [r["id"] for r in load_corpus() if not r.get("covered")]
    assert uncovered == []
