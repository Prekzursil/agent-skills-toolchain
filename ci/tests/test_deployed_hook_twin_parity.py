"""Pin the hook files that MUST stay byte-identical across the two deploy trees.

`hooks/**` and `agent-self/config/hooks/**` are two *separately installed*
copies of the same harness: `scripts/bootstrap-codespace.sh` copies `hooks/`
(and `commands/`) into `~/.claude`, while `agent-self/bootstrap.ps1` copies the
whole of `agent-self/config/` there. Nothing in CI compares them, and they are
NOT a full mirror -- ~70 hook dirs on one side, 21 on the other, and several
files carry deliberate, separately-reviewed extensions (a TEST_TAMPER_MODE gate,
a CLAIM_GUARD_MODE=block escalation, an MSYS path-conversion rule).

That makes a *partial* fix the real hazard: a defect fixed in one tree and left
live in the other is silently reachable on whichever box ran the other
bootstrap. The pairs below were byte-identical when this gate landed, so any
future divergence is drift, not design -- fix both or delete the pair from this
list with a reason.

Run (there is no repo-wide pytest autodiscovery; `.github/workflows/
skill-dual-write.yml` runs `pytest ci/tests` as a directory):

    pytest ci/tests/test_deployed_hook_twin_parity.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# (repo-root path, agent-self/config path) pairs that must match byte-for-byte.
PINNED_TWINS: tuple[tuple[str, str], ...] = (
    (
        "hooks/event-ledger/sessionstart-replay.py",
        "agent-self/config/hooks/event-ledger/sessionstart-replay.py",
    ),
    (
        "hooks/claim-guard/ledger-write.py",
        "agent-self/config/hooks/claim-guard/ledger-write.py",
    ),
    (
        "hooks/edit-validate/record.py",
        "agent-self/config/hooks/edit-validate/record.py",
    ),
    (
        "commands/orchestrate.md",
        "agent-self/config/commands/orchestrate.md",
    ),
)

# Pairs that legitimately DIFFER: the repo-root copy carries an extension that
# was reviewed on its own. Listed so the divergence is a recorded decision
# rather than an unnoticed drift, and used as this gate's detector control.
KNOWN_DIVERGENT: tuple[tuple[str, str, str], ...] = (
    (
        "hooks/test-tamper-guard/guard.py",
        "agent-self/config/hooks/test-tamper-guard/guard.py",
        "repo-root adds the TEST_TAMPER_MODE=block escalation",
    ),
    (
        "hooks/claim-guard/claim-check.py",
        "agent-self/config/hooks/claim-guard/claim-check.py",
        "repo-root adds the narrow CLAIM_GUARD_MODE=block escalation",
    ),
    (
        "hooks/cmd-rewrite/inject-nopager.py",
        "agent-self/config/hooks/cmd-rewrite/inject-nopager.py",
        "repo-root also hosts the MSYS path-conversion rule",
    ),
)


def read(rel: str) -> str:
    """Universal-newline read: parity must not depend on CRLF vs LF checkout."""
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize(("root", "mirror"), PINNED_TWINS, ids=lambda p: Path(p).name)
def test_pinned_twin_is_byte_identical(root: str, mirror: str) -> None:
    assert read(root) == read(mirror), (
        f"{root} and {mirror} have drifted. They were identical when this gate "
        "landed; fix BOTH trees, or move the pair to KNOWN_DIVERGENT with the "
        "reason the divergence is intended."
    )


@pytest.mark.parametrize(
    ("root", "mirror", "why"), KNOWN_DIVERGENT, ids=lambda p: Path(str(p)).name
)
def test_known_divergent_pair_still_diverges(root: str, mirror: str, why: str) -> None:
    """Detector control (single-signal-verification rule 3b).

    A parity gate whose comparator is broken passes silently. These three pairs
    are KNOWN to differ, so the comparator must report them as different; if one
    ever converges, that is news -- promote it to PINNED_TWINS.
    """
    assert read(root) != read(mirror), (
        f"{root} now equals {mirror} ({why} is gone?). Either the extension was "
        "removed -- promote the pair to PINNED_TWINS -- or this gate's comparator "
        "is broken and every PINNED_TWINS pass above is meaningless."
    )


@pytest.mark.parametrize(
    "rel",
    [p for pair in PINNED_TWINS for p in pair]
    + [p for triple in KNOWN_DIVERGENT for p in triple[:2]],
)
def test_every_listed_path_exists(rel: str) -> None:
    """A renamed or deleted file must fail loudly here rather than making the
    parametrized comparison above quietly vanish from the run."""
    assert (REPO_ROOT / rel).is_file(), f"{rel} is missing; this gate is stale"
