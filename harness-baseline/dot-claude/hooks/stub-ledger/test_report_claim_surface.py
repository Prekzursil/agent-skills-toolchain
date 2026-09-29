"""Both-states tests for the final-MESSAGE completion-claim surface (open loop b788a392).

The guard must SUPPRESS the stub ledger when the assistant genuinely claims completion, and must
NOT suppress it when the message merely quotes the phrase while discussing the guard. A test that
only checks one direction cannot tell a working discriminator from one that always returns True.

Polarity note: a completion claim is the INVERSE of a TODO marker. In prose the claim is REAL;
quoted or fenced it is a MENTION. Routing it through kind="marker" would invert this and suppress
every genuine claim, so the kind is pinned by an explicit test below.
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "_shared"))

from report import _real_completion_claim  # noqa: E402
from use_vs_mention import Context, is_real_occurrence  # noqa: E402


def test_genuine_claim_in_prose_is_real():
    """Known-good state: an ordinary assertion must still suppress the ledger."""
    assert _real_completion_claim("I wired it up and the feature is now complete.")


def test_backticked_mention_is_not_a_claim():
    """The regression b788a392 names: describing the guard must not trip the guard."""
    text = "The ledger stays silent when the final message says `is now complete`."
    assert not _real_completion_claim(text)


def test_fenced_mention_is_not_a_claim():
    text = "Example of a suppressing message:\n\n```\nthe feature is complete\n```\n\nThat is all."
    assert not _real_completion_claim(text)


def test_mixed_message_with_a_real_claim_still_counts():
    """A quoted example must not MASK a genuine claim elsewhere in the same message."""
    text = (
        "The guard fires on `is now complete` in backticks.\n\n"
        "Separately: I implemented the parser and it is now functional."
    )
    assert _real_completion_claim(text)


def test_no_claim_at_all_is_false():
    assert not _real_completion_claim(
        "Here is a status update with no completion language."
    )


def test_marker_polarity_would_be_wrong_here():
    """Pin the kind: 'marker' inverts the answer, which is why 'claim' exists.

    If this ever starts agreeing with kind='claim' in prose, the shared discriminator's polarity
    has changed and report.py must be re-examined.
    """
    text = "the feature is now complete"
    ctx = Context(source="assistant_message")
    span = (0, len(text))
    assert is_real_occurrence(text, span, ctx, kind="claim") is True
    assert is_real_occurrence(text, span, ctx, kind="marker") is False


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
