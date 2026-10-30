"""Pin the deploy-twin surface between the repo root and `agent-self/config/`.

`hooks/**` and `agent-self/config/hooks/**` are two *separately installed*
copies of the same harness: `scripts/bootstrap-codespace.sh` copies `hooks/`
(and `commands/`, `rules/`) into `~/.claude`, while `agent-self/bootstrap.ps1`
copies the repo-root `hooks/` as a base layer and then lays `agent-self/config/*`
over it as the winning curated layer. They are NOT a full mirror -- ~70 hook dirs
on one side, 21 on the other -- and several files carry deliberate, separately
reviewed extensions (a TEST_TAMPER_MODE gate, a CLAIM_GUARD_MODE=block
escalation, an MSYS path-conversion rule).

That makes a *partial* fix the real hazard: a defect fixed in one tree and left
live in the other is silently reachable on whichever box ran the other
bootstrap.

ROUND-3 EXTENSION (2026-08-13). This gate used to name 7 pairs by hand. The
surface is **195 pairs**, so 27 had drifted with nothing in CI to notice --
including `hooks/edit-validate/validate-stop.py` (sha1 vs sha256 for the same
dedupe key) and `hooks/precompact-basicmemory/capture.ps1`, where the repo-root
copy was deliberately reduced to a compatibility shim *whose own docstring says
it exists to stop the previous behaviour being revived* while the mirror still
ships that behaviour in full.

So the gate now DISCOVERS the whole surface from `git ls-files` and requires
every discovered pair to be either byte-identical or DECLARED. Consequences:

  * the 161 currently-identical pairs become a ratchet -- any of them drifting
    is a red build, up from 4 pairs before;
  * a NEW undeclared divergence cannot appear silently;
  * a declaration that no longer matches a real pair is flagged as stale.

Adding a row to `KNOWN_DIVERGENT` RECORDS a divergence, it does not fix one.
`command-center/slop-report/_r3_synctable.out.json` ranks every divergent pair
by whether it can be reconciled without losing content: 30 of the 34 cannot,
because each side holds bytes the other lacks in the same slot.

Run (there is no repo-wide pytest autodiscovery; `.github/workflows/
skill-dual-write.yml` runs `pytest ci/tests` as a directory):

    pytest ci/tests/test_deployed_hook_twin_parity.py -q
"""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_PREFIX = "agent-self/config/"
USER_HOME_TOKEN = "{{USER_HOME}}"

# Discovery floor. The surface measured 195 pairs at ab3667d5. A discovery that
# returns far fewer means the enumerator broke -- wrong cwd, git unavailable,
# the mirror tree renamed -- not that the repo got tidy. Fail closed: a gate
# that silently finds nothing to compare is the exact shape of no-op this repo
# has already shipped twice.
MIN_DISCOVERED_PAIRS = 150

# (repo-root path, agent-self/config path) pairs that must match byte-for-byte.
# Redundant with the discover-and-require-declaration rule below, and kept
# anyway: these four are the load-bearing ones, and naming them explicitly means
# a future "fix" that demotes one to KNOWN_DIVERGENT trips
# `test_pinned_pairs_are_not_also_declared_divergent` instead of passing quietly.
PINNED_TWINS: tuple[tuple[str, str], ...] = (
    (
        "hooks/event-ledger/sessionstart-replay.py",
        "agent-self/config/hooks/event-ledger/sessionstart-replay.py",
    ),
    # PROMOTED 2026-10-24 from KNOWN_DIVERGENT, where these five were RECORDED as
    # drifting rather than fixed. The mirror had taken the newer stop-hook.py and
    # sessionstart-replay.py while keeping a two-generations-old ledger.py and
    # note.py (233 L against the root's 441), so it ran a current stop-hook against
    # a stale ledger module -- a combination that existed nowhere real, and which
    # quality.yml:1055 and :1492 were gating green. Re-projected wholesale from the
    # root, so these are now ENFORCED identical instead of merely described.
    #
    # Nothing was lost. The mirror's test_ledger.py asserted `"ship the ledger" in
    # ctx`, i.e. that the goal WAS injected into replay context -- the root's own
    # comment records that as the leak it removed ("this check used to assert the
    # goal WAS injected -- it pinned the leak"). Its 10 assertion labels were a
    # strict subset of the root's 16. The divergence was a stale copy pinning a
    # fixed bug, not a variant worth keeping.
    (
        "hooks/event-ledger/ledger.py",
        "agent-self/config/hooks/event-ledger/ledger.py",
    ),
    (
        "hooks/event-ledger/note.py",
        "agent-self/config/hooks/event-ledger/note.py",
    ),
    (
        "hooks/event-ledger/prune-report.py",
        "agent-self/config/hooks/event-ledger/prune-report.py",
    ),
    (
        "hooks/event-ledger/test_ledger.py",
        "agent-self/config/hooks/event-ledger/test_ledger.py",
    ),
    (
        "hooks/event-ledger/test_prune_oats.py",
        "agent-self/config/hooks/event-ledger/test_prune_oats.py",
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

# Same relative path under both roots, but NOT twins: two different documents
# that happen to share a filename. Declared so the discovery rule below does not
# demand they converge.
NOT_TWINS: tuple[tuple[str, str, str], ...] = (
    (
        "AGENTS.md",
        "agent-self/config/AGENTS.md",
        "repo-root AGENTS.md is this repository's contributor guide; the "
        "agent-self copy is the deployed cross-tool behaviour contract",
    ),
    (
        "CLAUDE.md",
        "agent-self/config/CLAUDE.md",
        "repo-root CLAUDE.md is repo guidance; the agent-self copy is the "
        "deployed per-user CLAUDE.md",
    ),
)

# Pairs whose ONLY difference is the substitution `agent-self/bootstrap.ps1:4`
# performs at deploy time. `test_templated_pair_differs_only_by_the_token`
# proves that mechanically rather than taking the classification on trust.
TEMPLATED: tuple[tuple[str, str, str], ...] = (
    (
        "hooks/harness-trim/instructions-loaded-log.ps1",
        "agent-self/config/hooks/harness-trim/instructions-loaded-log.ps1",
        "log path is templated as {{USER_HOME}} in the deployable copy",
    ),
    (
        "hooks/inquisitiveness/prompt-guard.py",
        "agent-self/config/hooks/inquisitiveness/prompt-guard.py",
        "the docstring's install command is templated as {{USER_HOME}}",
    ),
)

# Pairs that legitimately -- or at least knowingly -- DIFFER. Listed so the
# divergence is a recorded decision rather than an unnoticed drift, and used as
# this gate's detector control.
#
# The first three predate round 3 and are reviewed extensions. The rest were
# found by the round-3 surface sweep and are recorded AS DRIFT: each reason
# states what was measured, not that the divergence was approved. Direction and
# sync-safety per pair: `command-center/slop-report/_r3_synctable.out.json`
# (measured at ab3667d5).
KNOWN_DIVERGENT: tuple[tuple[str, str, str], ...] = (
    (
        "hooks/test-tamper-guard/guard.py",
        "agent-self/config/hooks/test-tamper-guard/guard.py",
        "REVIEWED: repo-root adds the TEST_TAMPER_MODE=block escalation",
    ),
    (
        "hooks/claim-guard/claim-check.py",
        "agent-self/config/hooks/claim-guard/claim-check.py",
        "REVIEWED: repo-root adds the narrow CLAIM_GUARD_MODE=block escalation",
    ),
    (
        "hooks/cmd-rewrite/inject-nopager.py",
        "agent-self/config/hooks/cmd-rewrite/inject-nopager.py",
        "REVIEWED: repo-root also hosts the MSYS path-conversion rule",
    ),
    # --- round-3 sweep: recorded drift, not approved divergence --------------
    (
        "hooks/edit-validate/validate-stop.py",
        "agent-self/config/hooks/edit-validate/validate-stop.py",
        "DRIFT: repo-root hashes the wrapper name and the dedupe signature with "
        "hashlib.sha1(..., usedforsecurity=False); the mirror uses "
        "hashlib.sha256(...). Same two call sites, neither is a security use. "
        "Unreconciled: pick one and apply it to both",
    ),
    (
        "hooks/precompact-basicmemory/capture.ps1",
        "agent-self/config/hooks/precompact-basicmemory/capture.ps1",
        "DRIFT, highest severity in the sweep: repo-root is a compatibility "
        "shim that delegates to the shared dispatcher and says it exists so a "
        "cached hook definition cannot revive the previous capture behaviour -- "
        "and the mirror is exactly that previous behaviour, ~78 lines of it, "
        "still deployed by agent-self/bootstrap.ps1",
    ),
    (
        "hooks/memory-guard/scan.py",
        "agent-self/config/hooks/memory-guard/scan.py",
        "DRIFT: repo-root's allowlist includes 'deepscan', the mirror's does "
        "not; the mirror also reflows the tool-name folding comment",
    ),
    (
        "hooks/memory-guard/README.md",
        "agent-self/config/hooks/memory-guard/README.md",
        "DRIFT: documentation side of the same 'deepscan' allowlist divergence",
    ),
    (
        "hooks/memory-guard/test_scan.py",
        "agent-self/config/hooks/memory-guard/test_scan.py",
        "DRIFT: the mirror carries a '# nosemgrep: ...bidi...' suppression on "
        "the RIGHT-TO-LEFT-OVERRIDE test fixture; the repo root does not. The "
        "root is a strict subset, so root <- mirror would lose nothing",
    ),
    (
        "hooks/_golden/test_hooks.py",
        "agent-self/config/hooks/_golden/test_hooks.py",
        "DRIFT, two-directional: 2 root-only runs (8 lines), 1 mirror-only run "
        "(1 line), 11 replaced blocks",
    ),
    (
        "hooks/README.md",
        "agent-self/config/hooks/README.md",
        "DRIFT: one wholesale replaced block -- 171 root lines against 100 "
        "mirror lines describing the same hook inventory",
    ),
    (
        "hooks/claim-guard/README.md",
        "agent-self/config/hooks/claim-guard/README.md",
        "DRIFT, two-directional: documents the hook matcher as "
        "'Bash|PowerShell' on one side and 'Bash' on the other; 3 root-only "
        "and 2 mirror-only runs",
    ),
    (
        "hooks/test-tamper-guard/README.md",
        "agent-self/config/hooks/test-tamper-guard/README.md",
        "DRIFT: documentation side of the reviewed TEST_TAMPER_MODE extension, "
        "1 root-only run (8 lines) plus 1 replaced block. The code divergence "
        "above is REVIEWED; this doc divergence was not separately recorded",
    ),
    (
        "commands/agent-monitor.md",
        "agent-self/config/commands/agent-monitor.md",
        "DRIFT: 5 replaced blocks, no unique-run content on either side",
    ),
    (
        "commands/harness-audit.md",
        "agent-self/config/commands/harness-audit.md",
        "DRIFT: 1 root-only run (5 lines) plus 3 replaced blocks",
    ),
    (
        "commands/mcp-gui.md",
        "agent-self/config/commands/mcp-gui.md",
        "DRIFT: 5 replaced blocks, no unique-run content on either side",
    ),
    (
        "commands/python-review.md",
        "agent-self/config/commands/python-review.md",
        "DRIFT: 1 replaced block",
    ),
    (
        "rules/README.md",
        "agent-self/config/rules/README.md",
        "DRIFT: 4 root-only runs (56 lines) plus 6 replaced blocks",
    ),
    (
        "rules/common/testing.md",
        "agent-self/config/rules/common/testing.md",
        "DRIFT: repo-root carries the .coverage-thresholds.json SSOT text; the "
        "mirror still carries the retired flat '80%'. "
        "ci/tests/test_coverage_authority_consistency.py governs the root copy",
    ),
    (
        "rules/common/code-review.md",
        "agent-self/config/rules/common/code-review.md",
        "DRIFT, two-directional: same coverage-authority divergence as "
        "testing.md, AND the mirror adds go-reviewer / rust-reviewer rows to "
        "the agent table that the repo root does not have",
    ),
    (
        "rules/common/security.md",
        "agent-self/config/rules/common/security.md",
        "DRIFT: 2 root-only runs (42 lines), no replaced blocks -- the mirror "
        "is a strict subset, so mirror <- root would lose nothing",
    ),
    (
        "rules/common/coding-style.md",
        "agent-self/config/rules/common/coding-style.md",
        "DRIFT: 1 root-only run (7 lines) plus 1 replaced block",
    ),
    (
        "rules/common/git-workflow.md",
        "agent-self/config/rules/common/git-workflow.md",
        "DRIFT: 1 root-only run (40 lines) plus 1 replaced block",
    ),
    (
        "rules/common/hooks.md",
        "agent-self/config/rules/common/hooks.md",
        "DRIFT: 2 root-only runs (16 lines) plus 3 replaced blocks",
    ),
    (
        "rules/golang/coding-style.md",
        "agent-self/config/rules/golang/coding-style.md",
        "DRIFT: 1 root-only run (16 lines), no replaced blocks -- the mirror "
        "is a strict subset, so mirror <- root would lose nothing",
    ),
    (
        "rules/rust/coding-style.md",
        "agent-self/config/rules/rust/coding-style.md",
        "DRIFT: 2 root-only runs (8 lines), no replaced blocks -- the mirror "
        "is a strict subset, so mirror <- root would lose nothing",
    ),
)

DECLARED_DIVERGENT: tuple[tuple[str, str, str], ...] = (
    KNOWN_DIVERGENT + TEMPLATED + NOT_TWINS
)


def read(rel: str) -> str:
    """Universal-newline read: parity must not depend on CRLF vs LF checkout."""
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def discover_twin_pairs() -> tuple[tuple[str, str], ...]:
    """Every TRACKED file that exists under both roots at the same relative path.

    Enumerated from the index, not from the filesystem, so untracked scratch can
    never enter the surface and a clone sees exactly what CI sees.
    """
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    tracked = {p for p in raw.split("\0") if p}
    return tuple(
        (mirror[len(MIRROR_PREFIX) :], mirror)
        for mirror in sorted(tracked)
        if mirror.startswith(MIRROR_PREFIX) and mirror[len(MIRROR_PREFIX) :] in tracked
    )


def undeclared_divergences(
    pairs: tuple[tuple[str, str], ...],
    declared: frozenset[str],
    reader,
) -> list[str]:
    """Pure core of the ratchet, with `reader` injected so it is testable.

    A gate whose only evidence is "it passed on the real tree" cannot be shown to
    fire; `test_ratchet_detector_*` below exercise this function directly in both
    states.
    """
    return [
        root
        for root, mirror in pairs
        if root not in declared and reader(root) != reader(mirror)
    ]


def differs_only_by_token(root_text: str, mirror_text: str) -> bool:
    """True when `mirror_text` becomes `root_text` by one consistent expansion.

    Every differing line must carry the token in the mirror, the root line must
    match that line's prefix and suffix, and every such line must imply the SAME
    substituted value -- otherwise it is drift wearing a template's clothes.
    """
    root_lines = root_text.splitlines()
    mirror_lines = mirror_text.splitlines()
    if len(root_lines) != len(mirror_lines):
        return False
    substitutions = set()
    for root_line, mirror_line in zip(root_lines, mirror_lines):
        if root_line == mirror_line:
            continue
        if USER_HOME_TOKEN not in mirror_line:
            return False
        head, _, tail = mirror_line.partition(USER_HOME_TOKEN)
        if len(root_line) < len(head) + len(tail):
            return False
        if not (root_line.startswith(head) and root_line.endswith(tail)):
            return False
        substitutions.add(root_line[len(head) : len(root_line) - len(tail)])
    return len(substitutions) == 1


@pytest.mark.parametrize(("root", "mirror"), PINNED_TWINS, ids=lambda p: Path(p).name)
def test_pinned_twin_is_byte_identical(root: str, mirror: str) -> None:
    assert read(root) == read(mirror), (
        f"{root} and {mirror} have drifted. They were identical when this gate "
        "landed; fix BOTH trees, or move the pair to KNOWN_DIVERGENT with the "
        "reason the divergence is intended."
    )


@pytest.mark.parametrize(
    ("root", "mirror", "why"),
    DECLARED_DIVERGENT,
    ids=[t[0] for t in DECLARED_DIVERGENT],
)
def test_declared_divergent_pair_still_diverges(
    root: str, mirror: str, why: str
) -> None:
    """Detector control (single-signal-verification rule 3b).

    A parity gate whose comparator is broken passes silently. Every pair here is
    KNOWN to differ, so the comparator must report them as different; if one
    ever converges, that is news -- delete the row (and pin it, if it should stay
    converged).
    """
    assert read(root) != read(mirror), (
        f"{root} now equals {mirror} ({why} is gone?). Either the divergence was "
        "resolved -- delete this row, and add the pair to PINNED_TWINS if it must "
        "stay resolved -- or this gate's comparator is broken and every pass "
        "above is meaningless."
    )


@pytest.mark.parametrize(
    "rel",
    [p for pair in PINNED_TWINS for p in pair]
    + [p for triple in DECLARED_DIVERGENT for p in triple[:2]],
)
def test_every_listed_path_exists(rel: str) -> None:
    """A renamed or deleted file must fail loudly here rather than making the
    parametrized comparison above quietly vanish from the run."""
    assert (REPO_ROOT / rel).is_file(), f"{rel} is missing; this gate is stale"


def test_twin_surface_discovery_is_plausible() -> None:
    """Fail closed on a broken enumerator instead of reporting a clean surface."""
    pairs = discover_twin_pairs()
    assert len(pairs) >= MIN_DISCOVERED_PAIRS, (
        f"discovered only {len(pairs)} twin pairs under {MIRROR_PREFIX}, below the "
        f"{MIN_DISCOVERED_PAIRS} floor. Either the mirror tree was restructured -- "
        "in which case lower the floor deliberately, in a commit that says why -- "
        "or discovery is broken and every parity pass in this file is vacuous."
    )
    pinned_roots = {root for root, _ in PINNED_TWINS}
    assert pinned_roots <= {root for root, _ in pairs}, (
        "discovery missed a pair this gate already pins by hand, so it cannot be "
        "trusted to find the ones nobody listed"
    )


def test_no_undeclared_divergence() -> None:
    """The ratchet: every discovered pair is byte-identical or DECLARED.

    This is the hole round 3 closed. Before it, 27 pairs had drifted with the
    gate green, because the gate only ever looked at the 7 pairs it named.
    """
    pairs = discover_twin_pairs()
    assert pairs, "no twin pairs discovered at all -- see the plausibility test"
    declared = frozenset(
        [root for root, _ in PINNED_TWINS] + [t[0] for t in DECLARED_DIVERGENT]
    )
    undeclared = undeclared_divergences(pairs, declared, read)
    assert not undeclared, (
        f"{len(undeclared)} deploy-twin pair(s) diverge without a declaration: "
        f"{undeclared}. Both trees are deployed, so a fix landed in one and not "
        "the other is live on whichever box ran the other bootstrap. Either "
        "reconcile the pair, or add it to KNOWN_DIVERGENT with what you measured "
        "-- and check command-center/slop-report/_r3_synctable.out.json first: "
        "for most of this surface a mechanical sync deletes content."
    )


def test_no_stale_declaration() -> None:
    """A declared pair that discovery no longer finds is a rotten row."""
    discovered = {root for root, _ in discover_twin_pairs()}
    declared = [root for root, _ in PINNED_TWINS] + [t[0] for t in DECLARED_DIVERGENT]
    stale = sorted(set(declared) - discovered)
    assert not stale, (
        f"declared pairs that are no longer a tracked twin: {stale}. A stale row "
        "silently exempts a path that may have been renamed back later."
    )


def test_pinned_pairs_are_not_also_declared_divergent() -> None:
    """Tripwire: a pinned pair must never be 'fixed' by demoting it."""
    pinned = {root for root, _ in PINNED_TWINS}
    demoted = pinned & {t[0] for t in DECLARED_DIVERGENT}
    assert not demoted, (
        f"{sorted(demoted)} is both PINNED_TWINS and declared divergent. That "
        "combination makes the pin unenforceable -- resolve which one it is."
    )


def test_declared_rows_are_unique() -> None:
    """Two rows for one path let a later edit fix one and leave the other live."""
    roots = [t[0] for t in DECLARED_DIVERGENT]
    dupes = sorted({r for r in roots if roots.count(r) > 1})
    assert not dupes, f"duplicate declaration rows: {dupes}"


def test_declared_mirror_path_matches_its_root() -> None:
    """A row whose two paths are not actually twins exempts the wrong file."""
    bad = [
        (root, mirror)
        for root, mirror, _ in DECLARED_DIVERGENT
        if mirror != MIRROR_PREFIX + root
    ]
    assert not bad, f"declaration rows whose mirror path is not the twin: {bad}"


@pytest.mark.parametrize(
    ("root", "mirror", "why"), TEMPLATED, ids=[t[0] for t in TEMPLATED]
)
def test_templated_pair_differs_only_by_the_token(
    root: str, mirror: str, why: str
) -> None:
    """`{{USER_HOME}}` is an exemption that must be earned, not asserted.

    Without this, "it's just templating" would be a free pass anyone could write
    next to a real behaviour change in the same file.
    """
    assert differs_only_by_token(read(root), read(mirror)), (
        f"{root} vs {mirror} is declared TEMPLATED ({why}) but the difference is "
        "not one consistent {{USER_HOME}} expansion. Move it to KNOWN_DIVERGENT "
        "with what actually changed."
    )


def test_ratchet_detector_fires_on_an_undeclared_divergence() -> None:
    """Both-states control, broken half: the ratchet must report a real gap."""
    fake = {"a.py": "one", "agent-self/config/a.py": "two"}
    found = undeclared_divergences(
        (("a.py", "agent-self/config/a.py"),), frozenset(), fake.__getitem__
    )
    assert found == ["a.py"]


def test_ratchet_detector_is_silent_when_declared_or_identical() -> None:
    """Both-states control, clean half: no false positive from either exemption."""
    diverging = {"a.py": "one", "agent-self/config/a.py": "two"}
    assert (
        undeclared_divergences(
            (("a.py", "agent-self/config/a.py"),),
            frozenset({"a.py"}),
            diverging.__getitem__,
        )
        == []
    )
    same = {"b.py": "same", "agent-self/config/b.py": "same"}
    assert (
        undeclared_divergences(
            (("b.py", "agent-self/config/b.py"),), frozenset(), same.__getitem__
        )
        == []
    )


def test_template_detector_distinguishes_templating_from_drift() -> None:
    """Both-states control for the {{USER_HOME}} exemption."""
    assert differs_only_by_token("x /home/me/a\ny", "x {{USER_HOME}}/a\ny")
    # a real change on a second line is not templating
    assert not differs_only_by_token("x /home/me/a\nkeep", "x {{USER_HOME}}/a\nCHANGED")
    # two different expansions in one file is not one substitution
    assert not differs_only_by_token(
        "/home/me/a\n/home/you/b", "{{USER_HOME}}/a\n{{USER_HOME}}/b"
    )
    # a differing line with no token at all is drift
    assert not differs_only_by_token("a", "b")
