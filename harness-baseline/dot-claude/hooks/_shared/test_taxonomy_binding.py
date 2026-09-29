#!/usr/bin/env python3
"""Binding test: proves failure_taxonomy (C16) is LOAD-BEARING for completion.py.

Before this wiring, `failure_taxonomy.py` had ZERO live importers -- 9,859 B of tested,
green, inert code -- while `completion.py` carried its own copy of the `severed-stream`
literal. Two spellings of one concept, free to drift, with nothing to notice.

A test that merely asserted `reason.startswith("severed-stream")` would pass on BOTH the
wired and the hardcoded version (the constant's value equals the old literal), so it would
prove nothing. These two tests are constructed so they can only pass if the value genuinely
ORIGINATES in the taxonomy:

  1. IDENTITY  -- completion.SEVERED_STREAM is the same object as
                  failure_taxonomy.SEVERED_STREAM.
  2. MUTATION  -- rebind completion.SEVERED_STREAM and the verdict reason FOLLOWS it. A
                  hardcoded literal cannot follow.

Run:  python test_taxonomy_binding.py      (also collects under pytest)
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

import completion  # noqa: E402
import failure_taxonomy  # noqa: E402

MISSING = str(THIS / "__does_not_exist__.md")


def _severed_verdict():
    """The exit-0-with-no-artifact case -- completion.py's severed-stream branch."""
    return completion.classify(
        artifact=MISSING, sentinel="UNIT-COMPLETE", exit_code=0, detector_ok=True
    )


def test_identity_completion_reuses_the_taxonomy_constant():
    assert completion.SEVERED_STREAM is failure_taxonomy.SEVERED_STREAM, (
        "completion.py must take the class label FROM failure_taxonomy, not keep its own copy"
    )
    assert failure_taxonomy.SEVERED_STREAM == "severed-stream"


def test_mutating_the_constant_changes_the_verdict_reason():
    v = _severed_verdict()
    assert v.state == completion.FAILED, f"expected FAILED, got {v.state}"
    assert v.reason.startswith(failure_taxonomy.SEVERED_STREAM), v.reason

    original = completion.SEVERED_STREAM
    try:
        completion.SEVERED_STREAM = "MUTATED-CLASS-LABEL"
        mutated = _severed_verdict()
        assert mutated.reason.startswith("MUTATED-CLASS-LABEL"), (
            "the verdict reason did NOT follow the rebound constant -- completion.py is still "
            f"using a hardcoded literal: {mutated.reason!r}"
        )
    finally:
        completion.SEVERED_STREAM = original

    restored = _severed_verdict()
    assert restored.reason.startswith("severed-stream"), restored.reason


def main() -> int:
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK  {name}")
            except AssertionError as exc:
                failures.append((name, str(exc)))
                print(f"  FAIL {name}: {exc}")
    if failures:
        print(f"\nFAILED:taxonomy-binding {len(failures)} of 2 test(s) failed")
        return 1
    print("\nSUCCESS:taxonomy-binding 2/2 -- C16 is load-bearing for completion.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
