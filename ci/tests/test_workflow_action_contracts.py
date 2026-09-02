"""A third-party action can silently ignore, or silently truncate, what we asked it for.

Both cases below were live in this repository and neither failed loudly: the job
stayed green while the thing it advertised was not actually done.  A pinned SHA is
not a contract -- these tests pin the CONTRACT.

There is no repo-wide pytest autodiscovery here.  This file runs because
``.github/workflows/skill-dual-write.yml`` invokes the whole directory
(``python -m pytest ci/tests tools/d001-dual-write/tests -q``) on every
``pull_request``; ``ci/tests/test_ci_wiring.py`` separately pins that the step keeps
covering this directory, so the wiring cannot rot silently.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY = REPO_ROOT / ".github" / "workflows" / "quality.yml"
AUTOFIX = REPO_ROOT / ".github" / "workflows" / "autofix-models.yml"

# Keep the two gitleaks call sites on one version.  The action gets it via the
# GITLEAKS_VERSION env; the range-independent scan downloads the same tag.
GITLEAKS_PINNED = "8.30.1"


def quality_text() -> str:
    return QUALITY.read_text(encoding="utf-8")


def autofix_text() -> str:
    return AUTOFIX.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# gate-secrets: the verdict must not depend on the action's chosen commit range
# --------------------------------------------------------------------------
#
# Known-broken state: the ONLY secret scan was
# ``gitleaks/gitleaks-action@<sha>``.  At v3.0.0 that action issues exactly one
# unpaginated ``GET /repos/{owner}/{repo}/pulls/{pull_number}/commits`` and uses
# the LAST SHA OF PAGE 1 as its head endpoint (src/gitleaks.js:160-172; the same
# call is in the executed bundle dist/index.js; ``octokit.paginate`` has zero call
# sites in either).  GitHub's default page size for that endpoint is 30, so on a
# PR with >30 commits the scan stops at commit 30 and a secret added in commit 31
# is never assessed -- while the job exits 0.  The action's only range knob is
# ``BASE_REF`` and it moves the BASE end only (src/gitleaks.js:174-178), so no
# configuration of the action can fix this.


SCAN_CMD = (
    '"$RUNNER_TEMP/gitleaks" git --config .gitleaks.toml --redact --exit-code 1 \\\n'
    '            --log-opts="--full-history HEAD" .'
)
# HEAD-scoped on purpose: `gitleaks git` defaults to `git log --all`, and
# `fetch-depth: 0` fetches every remote branch, so without this the gate went red on
# refs the PR does not carry (the 802 MB P2 capture branches, 02.09.2026).
SCAN_SCOPE = '--log-opts="--full-history HEAD"'


def test_secrets_gate_runs_a_range_independent_full_history_scan() -> None:
    text = quality_text()
    assert "git --config .gitleaks.toml" in text, (
        "gate-secrets has no range-independent scan; its verdict then comes only "
        "from gitleaks-action, whose PR commit range truncates at 30 commits"
    )


def test_range_independent_scan_fails_the_job_on_a_finding() -> None:
    """A scan that cannot go red is decoration, not a gate."""
    text = quality_text()
    assert SCAN_CMD in text, f"expected the exact invocation: {SCAN_CMD}"
    assert SCAN_SCOPE in text, "the full-history scan must be scoped to HEAD ancestors"
    assert "--all" not in text.split(SCAN_CMD)[1].split("deps:")[0], (
        "the range-independent scan must not re-widen to every fetched ref"
    )


def test_range_independent_scan_uses_the_same_pinned_gitleaks_as_the_action() -> None:
    """Two scanners on two versions would disagree about the allowlist."""
    text = quality_text()
    assert f'GITLEAKS_VERSION: "{GITLEAKS_PINNED}"' in text
    assert text.count(f'GITLEAKS_VERSION: "{GITLEAKS_PINNED}"') >= 2, (
        "the action and the full-history scan must pin the same gitleaks version"
    )
    assert (
        "gitleaks/releases/download/v${GITLEAKS_VERSION}/"
        "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" in text
    ), "the download URL must derive from GITLEAKS_VERSION, not a second literal"


def test_the_downloaded_gitleaks_tarball_is_digest_pinned() -> None:
    """`curl | tar` is outside the "all actions are SHA-pinned" rule at the top of
    quality.yml, so the tarball carries its own digest.  Without the `sha256sum -c`
    the secret gate would execute whatever bytes that URL serves.  The expected
    digest was taken from the release's checksums.txt AND independently recomputed
    from the downloaded artifact.
    """
    text = quality_text()
    assert "GITLEAKS_SHA256:" in text, "the gitleaks tarball is not digest-pinned"
    assert "sha256sum -c -" in text, (
        "the digest is declared but never checked; verify before extracting"
    )
    verify = text.index("sha256sum -c -")
    extract = text.index('tar -xzf "$RUNNER_TEMP/gitleaks.tar.gz"')
    assert verify < extract, "the digest must be checked BEFORE extraction"


def test_secrets_job_still_fetches_full_history_for_that_scan() -> None:
    """`gitleaks git` over a shallow clone would silently scan almost nothing."""
    text = quality_text()
    secrets_block = text.split("  secrets:\n", 1)[1].split("\n  deps:", 1)[0]
    assert "fetch-depth: 0" in secrets_block


# --------------------------------------------------------------------------
# autofix-models: a supplied input the pinned action does not declare is DROPPED
# --------------------------------------------------------------------------
#
# Known-broken state: the workflow pinned ``actions/ai-inference@v1`` while
# supplying ``max-completion-tokens: "2000"``.  v1's action.yml declares only
# ``max-tokens`` (default "200"), so the runner warned ``Unexpected input(s)``,
# injected the 200 default, and the request went out capped at 200 tokens -- an
# order of magnitude below the configured allowance, silently truncating the patch.
# v2 declares ``max-completion-tokens`` (action.yml), reads it (src/main.ts) and
# sends it as ``max_completion_tokens`` (src/inference.ts), so the pair is coherent.


def test_ai_inference_ref_declares_the_token_input_the_workflow_supplies() -> None:
    text = autofix_text()
    if "max-completion-tokens:" not in text:
        return  # input no longer supplied -> nothing to keep coherent
    assert "actions/ai-inference@v1" not in text, (
        "ai-inference v1 declares only `max-tokens`; a supplied "
        "`max-completion-tokens` is dropped and the real cap silently becomes 200"
    )


def test_autofix_supplies_exactly_one_token_allowance_input() -> None:
    """`max-tokens` and `max-completion-tokens` together are ambiguous."""
    text = autofix_text()
    assert not ("max-tokens:" in text and "max-completion-tokens:" in text)
