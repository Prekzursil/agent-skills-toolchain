"""Both-states tests for the fan-out completeness gate.

A gate is only trustworthy once it has been shown to FIRE on a known-broken artifact AND stay
SILENT on a known-good one. A probe that is quiet in both states measures nothing — that is not a
hypothetical, it nearly shipped as verification in this repo's history.

Every rejection test below is therefore paired with an acceptance test on the SAME artifact,
mutated minimally, so the test proves discrimination rather than mere refusal.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gate import gate, parse_block  # noqa: E402

TERSE = """```verdict
id: A01
audit_verdict: CONFIRMED
confidence: likely
```
UNIT-COMPLETE: AUD-DISP-A01
"""

VERBOSE = (
    "# Dossier\n\n" + ("Lorem ipsum evidence paragraph. " * 120) + "\n\n"
    "```verdict\nid: B02\naudit_verdict: REFUTED\nconfidence: very-likely\n```\n"
    "UNIT-COMPLETE: AUD-DISP-B02\n"
)


def test_terse_artifact_passes_structural_gate():
    """The regression that motivated this module: 382-byte artifacts are VALID."""
    r = gate(
        TERSE,
        "AUD-DISP-A01",
        fence="verdict",
        required_fields=("id", "audit_verdict", "confidence"),
    )
    assert r.ok, r.reason
    assert len(TERSE.encode()) < 800, (
        "fixture must stay below the old byte floor to be meaningful"
    )


def test_verbose_artifact_passes_same_gate():
    """Both lanes pass the SAME gate — the old floor discriminated by verbosity, not validity."""
    assert gate(
        VERBOSE,
        "AUD-DISP-B02",
        fence="verdict",
        required_fields=("id", "audit_verdict", "confidence"),
    ).ok


def test_truncated_artifact_is_rejected():
    """Known-broken state: the fix for the byte floor must still catch real truncation."""
    r = gate(TERSE[: len(TERSE) // 2], "AUD-DISP-A01", fence="verdict")
    assert not r.ok and "sentinel" in r.reason


def test_missing_required_field_is_rejected():
    """A long-but-malformed artifact must fail — length alone can never establish completeness."""
    broken = TERSE.replace("audit_verdict: CONFIRMED", "audit_verdict:")
    r = gate(
        broken,
        "AUD-DISP-A01",
        fence="verdict",
        required_fields=("id", "audit_verdict", "confidence"),
    )
    assert not r.ok and "audit_verdict" in r.reason


def test_sentinel_from_a_different_unit_is_rejected():
    """A results-directory harvest must not credit a unit with a sibling's artifact."""
    assert not gate(TERSE, "AUD-DISP-ZZZ", fence="verdict").ok


def test_missing_fence_block_is_rejected_but_sentinel_only_mode_passes():
    """Fence enforcement is opt-in: a prose lane with no block is legitimately gated on the sentinel."""
    prose = "some findings\nUNIT-COMPLETE: PROSE-1\n"
    assert not gate(prose, "PROSE-1", fence="verdict").ok
    assert gate(prose, "PROSE-1").ok


def test_parse_block_reads_the_field_not_the_document():
    """Use-vs-mention: a token discussed in prose must not be read as that field's value."""
    doc = (
        "The auditor may propose B_SUBSUMES_A when the reverse direction is stronger.\n"
        "```verdict\nproposed_fold: NONE\naudit_verdict: NON_FOLD_UPHELD\n```\n"
        "UNIT-COMPLETE: X1\n"
    )
    fields = parse_block(doc, "verdict")
    assert fields["proposed_fold"] == "NONE", (
        "must read the field, not grep the document"
    )
    assert "B_SUBSUMES_A" in doc, (
        "fixture must contain the decoy for the test to be meaningful"
    )


def test_explicit_min_bytes_still_available_when_a_lane_justifies_it():
    assert not gate(TERSE, "AUD-DISP-A01", min_bytes=10_000).ok
    assert gate(TERSE, "AUD-DISP-A01", min_bytes=10).ok


if __name__ == "__main__":
    import traceback

    fns = [
        v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)
    ]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n  {len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
