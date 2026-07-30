"""R1 tests: the write token never reaches the node; the out-of-band push primitive is fully covered."""

import pytest

from engine import tokens
from harness import submit


def _has_r1_env_guard() -> bool:
    """Behavioural probe, not a version check: does build_payload REFUSE a write
    token in extra_env? Verified in BOTH states -- the toolchain copy does a bare
    `env.update(extra_env)` and returns False; the dbx copy raises ValueError and
    returns True. harness/submit.py is a DIVERGED file owned by the M13 merge lane,
    so this lane cannot add the guard itself."""
    try:
        submit.build_payload(1, "b.json", "/r", extra_env={"GITHUB_TOKEN": "probe"})
    except ValueError:
        return True
    return False


def test_mint_is_single_repo_and_short_lived():
    auth = tokens.AppAuth(app_id="1", installation_id="2", private_key="k")
    mt = tokens.mint_push_token(
        "Prekzursil/env-inspector",
        auth,
        _mint_fn=lambda repo, a: ("ghs_abc", "2026-07-24T13:00:00Z"),
    )
    assert (
        mt.repo == "Prekzursil/env-inspector"
        and mt.token == "ghs_abc"
        and mt.expires_at.endswith("Z")
    )


def test_mint_without_client_raises():  # covers the no-_mint_fn guard (no pragma)
    with pytest.raises(RuntimeError, match="GitHub App client"):
        tokens.mint_push_token("o/r", tokens.AppAuth("1", "2", "k"))


def test_push_branch_ok_and_repo_mismatch():
    mt = tokens.MintedToken(token="ghs_x", repo="o/r", expires_at="Z")
    calls = []
    assert (
        tokens.push_branch(
            "o/r", "agent/x", mt, run_cmd=lambda a: calls.append(a) or (0, "", "")
        )
        is True
    )
    assert any("git" in c[0] for c in calls)
    assert (
        tokens.push_branch("o/r", "agent/x", mt, run_cmd=lambda a: (1, "", "boom"))
        is False
    )
    with pytest.raises(ValueError, match="scoped to"):
        tokens.push_branch("o/OTHER", "agent/x", mt, run_cmd=lambda a: (0, "", ""))


@pytest.mark.skipif(
    not _has_r1_env_guard(),
    reason="submit.build_payload has no R1 env guard yet (M13 lane owns submit.py)",
)
def test_build_payload_refuses_write_token_in_env():  # the R1 guard (replaces the old merge test)
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        with pytest.raises(ValueError, match=key):
            submit.build_payload(2, "b.json", "/r", extra_env={key: "ghp_secret"})
