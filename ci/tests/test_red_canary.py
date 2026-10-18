"""RED CANARY -- a deliberately failing test that proves CI can go RED.

Owner audit 2026-10-18 (slug: ci-quality-red-proof). This file exists ONLY on
branch ``ci/red-canary`` and is run ONLY by ``.github/workflows/red-canary.yml``
(``on: push: branches: [ci/red-canary]``). Its purpose is a one-shot
end-to-end propagation proof: a failing assertion on a pushed branch must
produce a RED check run with a non-zero conclusion. A gate that has never
been observed red is indistinguishable from a no-op.

SELF-DELETING NOTE
------------------
To return to green: DELETE THIS FILE (and ``.github/workflows/red-canary.yml``
too, if you want the whole canary gone). Nothing else in the repo references
either file. Do NOT "fix" the assertion below -- the failure is the feature.
The branch is deliberately left up, unmerged, as evidence for the owner.

This file must never be merged to main, and no other suite imports it.
"""

CANARY_BRANCH = "ci/red-canary"


def test_red_canary_deliberate_failure():
    """Intentionally fails. See module docstring before touching this."""
    assert 1 == 2, (
        "RED CANARY fired (expected). This assertion is deliberately "
        f"impossible and lives only on {CANARY_BRANCH}; see the module "
        "docstring for the self-deleting note."
    )
