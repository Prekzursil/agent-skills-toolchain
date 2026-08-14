"""Both-states proof for ``ci/check_skill_render_traps.py`` and for its CI wiring.

WHY THIS FILE EXISTS.  The SKILLS2 lane DIAGNOSED two render-path traps and then
recorded the diagnosis as prose in ``writing-skills/SKILL.md``.  Prose is not
reachable: nothing executes it, so the next skill to ship either defect goes dark
in silence, exactly as ``bc-drive-plus`` and ``cv-studio`` already did.  This suite
is what turns "diagnosed" into "gated", and it is what makes the gate CREDIBLE --
a green checker proves nothing until each of its rules has been seen to FIRE.

The controls are deliberately NOT synthetic mutations of a healthy file.  Mutating
a good file into the shape your own regex was written to catch demonstrates
self-consistency, not discrimination; that mistake was made once already in this
program and is recorded in ``SKILLS2-ROUND4-BUILD.md``.  Instead, each rule is
proven against the REAL blob that actually shipped the defect and the REAL blob
that fixed it, both read out of this repository's own history:

  * R1 ``comment-truncation``       ``ff14d2a6^`` -> ``ff14d2a6``  (bc-drive-plus)
  * R2 ``block-scalar-in-invalid``  ``878cd621^`` -> ``878cd621``  (cv-studio)

``1baa7ad5`` is the commit that reads like cv-studio's fix and it is **not** an
ancestor of ``main`` -- it is the pre-squash branch commit (``merge-base
--is-ancestor`` rc=1).  Pinning it would resolve on a developer box and fail in
CI.  The squashed twin ``878cd621`` is pinned instead, and this note is kept so the
trap is not re-walked.

These git-backed tests FAIL LOUD rather than ``skip`` when a blob cannot be
resolved.  A skip would make the control silently vanish in a shallow clone, which
is the no-op-detector shape the whole suite exists to prevent.
``.github/workflows/skill-dual-write.yml`` checks out with ``fetch-depth: 0``.

Run (there is no repo-wide pytest autodiscovery; the workflow runs ``pytest
ci/tests`` as a directory AND names this file explicitly)::

    python -m pytest ci/tests/test_skill_render_traps.py -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "ci" / "check_skill_render_traps.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

#: The two wires that make this gate reachable.  The directory glob in the workflow
#: already collects this file, but the workflow's own comments record that the glob
#: is one refactor away from not containing a given file -- so the explicit names
#: are the durable wire and these pin them.
WORKFLOW_MARKERS = (
    "python -m pytest ci/tests/test_skill_render_traps.py -q",
    "python ci/check_skill_render_traps.py",
)

sys.path.insert(0, str(GATE.parent))
import check_skill_render_traps as gate  # noqa: E402

#: rule -> (broken rev, fixed rev, path, skill name)
HISTORICAL_CASES = {
    gate.RULE_COMMENT_TRUNCATION: (
        "ff14d2a6^",
        "ff14d2a6",
        ".agents/skills/bc-drive-plus/SKILL.md",
        "bc-drive-plus",
    ),
    gate.RULE_BLOCK_IN_INVALID: (
        "878cd621^",
        "878cd621",
        "skills/cv-studio/SKILL.md",
        "cv-studio",
    ),
}


def _blob(rev: str, path: str) -> bytes:
    """Read a stored blob, failing loud with an actionable message."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{rev}:{path}"],
        capture_output=True,
    )
    assert proc.returncode == 0, (
        f"cannot resolve {rev}:{path} -- this control needs full history "
        f"(actions/checkout with fetch-depth: 0). git said: "
        f"{proc.stderr.decode('utf-8', 'replace')[:200]}"
    )
    return proc.stdout


def _root_with(tmp_path: Path, name: str, skill: str, payload: bytes | str) -> Path:
    """Materialise a one-skill root.  Bytes are written verbatim.

    Writing BYTES (not text) keeps the stored blob's LF endings intact: a Windows
    text write would re-insert CRLF and silently change what is measured.
    """
    root = tmp_path / name
    (root / skill).mkdir(parents=True)
    target = root / skill / "SKILL.md"
    if isinstance(payload, bytes):
        target.write_bytes(payload)
    else:
        target.write_text(payload, encoding="utf-8", newline="")
    return root


def _run(root: Path) -> tuple[int, list[dict[str, object]]]:
    files = gate.collect([root])
    violations, _advisory = gate.evaluate(files)
    return (gate.EXIT_VIOLATION if violations else gate.EXIT_OK), violations


def _rules(violations: list[dict[str, object]]) -> set[str]:
    return {str(v["rule"]) for v in violations}


# --------------------------------------------------------------------------
# HEALTHY CONTROL.  Without this, a permanently-red gate would satisfy every
# broken-direction test below.
# --------------------------------------------------------------------------


def test_the_real_repository_is_green() -> None:
    exit_code = gate.main([])
    assert exit_code == gate.EXIT_OK


def test_the_real_repository_measures_a_plausible_number_of_files() -> None:
    """A count, not a boolean: an empty or tiny walk must not read as parity.

    Four successive probes in this program agreed with each other and were all
    wrong because they counted the wrong collection.  A plausibility floor is the
    cheapest guard against that.
    """
    files = gate.collect(list(gate.DEFAULT_ROOTS))
    assert len(files) > 300, f"only {len(files)} SKILL.md found; the walk is wrong"


# --------------------------------------------------------------------------
# BROKEN DIRECTION, against the blobs that really shipped each defect.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rule", sorted(HISTORICAL_CASES))
def test_historical_broken_blob_fires_that_rule(rule: str, tmp_path: Path) -> None:
    broken_rev, _fixed_rev, path, skill = HISTORICAL_CASES[rule]
    root = _root_with(tmp_path, "broken", skill, _blob(broken_rev, path))
    exit_code, violations = _run(root)
    assert exit_code == gate.EXIT_VIOLATION
    assert rule in _rules(violations), (
        f"{broken_rev}:{path} shipped {rule} and the gate did not see it"
    )


@pytest.mark.parametrize("rule", sorted(HISTORICAL_CASES))
def test_historical_fixed_blob_is_silent(rule: str, tmp_path: Path) -> None:
    _broken_rev, fixed_rev, path, skill = HISTORICAL_CASES[rule]
    root = _root_with(tmp_path, "fixed", skill, _blob(fixed_rev, path))
    exit_code, violations = _run(root)
    assert exit_code == gate.EXIT_OK, f"false positive on the FIXED blob: {violations}"


def test_every_blocking_rule_has_a_historical_red_proof() -> None:
    """A rule with no red proof is a rule nobody has ever seen fire."""
    declared = {gate.RULE_COMMENT_TRUNCATION, gate.RULE_BLOCK_IN_INVALID}
    assert declared == set(HISTORICAL_CASES)


# --------------------------------------------------------------------------
# DISCRIMINATION.  These separate a targeted rule from one that reddens on
# anything nearby -- the difference between a gate and a tripwire.
# --------------------------------------------------------------------------


def test_hash_without_leading_whitespace_does_not_fire(tmp_path: Path) -> None:
    """``foo#bar`` is a literal ``#`` in YAML and renders in full.

    This is what proves the rule is not a naive ``"#" in value`` substring test.
    """
    body = "---\nname: t\ndescription: Use when tag#1 or C# is involved\n---\n\n# t\n"
    exit_code, violations = _run(_root_with(tmp_path, "r", "t", body))
    assert exit_code == gate.EXIT_OK, violations


def test_hash_inside_a_quoted_scalar_does_not_fire(tmp_path: Path) -> None:
    """A quote closes the comment trap; the fix the gate recommends must pass it."""
    body = '---\nname: t\ndescription: "Use when X #hashtag is meant literally"\n---\n\n# t\n'
    exit_code, violations = _run(_root_with(tmp_path, "r", "t", body))
    assert exit_code == gate.EXIT_OK, violations


def test_block_scalar_in_VALID_frontmatter_does_not_fire(tmp_path: Path) -> None:
    """The measured mechanism is the INTERSECTION, not the fold.

    11 of the 12 live folded-scalar skills render in full.  Blocking on folds alone
    would be the refuted claim re-shipped as code.
    """
    body = (
        "---\nname: t\ndescription: >\n  Use when a folded scalar is fine\n---\n\n# t\n"
    )
    exit_code, violations = _run(_root_with(tmp_path, "r", "t", body))
    assert exit_code == gate.EXIT_OK, violations


def test_strict_invalid_with_a_plain_description_is_advisory_only(
    tmp_path: Path,
) -> None:
    """5 of 6 such live skills render in full, so this must not block.

    Shipping the opposite claim is the defect the refutation stage blocked on.
    """
    body = "---\nname: t\ndescription: Use when X\nlicense: MIT (skill). Engines: RenderCV\n---\n\n# t\n"
    root = _root_with(tmp_path, "r", "t", body)
    files = gate.collect([root])
    violations, advisory = gate.evaluate(files)
    assert violations == []
    assert advisory["strict_invalid_count"] == 1


def test_comment_trap_on_a_continuation_line_still_fires(tmp_path: Path) -> None:
    """A plain scalar can wrap; the trap can sit on any of its lines."""
    body = "---\nname: t\ndescription: Use when X\n  and also Y #eaten\n---\n\n# t\n"
    exit_code, violations = _run(_root_with(tmp_path, "r", "t", body))
    assert exit_code == gate.EXIT_VIOLATION
    assert gate.RULE_COMMENT_TRUNCATION in _rules(violations)


def test_when_to_use_is_charged_too(tmp_path: Path) -> None:
    """The per-entry budget covers description + when_to_use, so both are gated."""
    body = "---\nname: t\ndescription: Use when X\nwhen_to_use: after Y #eaten\n---\n\n# t\n"
    exit_code, violations = _run(_root_with(tmp_path, "r", "t", body))
    assert exit_code == gate.EXIT_VIOLATION
    assert gate.RULE_COMMENT_TRUNCATION in _rules(violations)


# --------------------------------------------------------------------------
# FAIL CLOSED.  "Cannot measure" must never render as "clean".
# --------------------------------------------------------------------------


def test_empty_walk_is_a_configuration_error(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(gate.ConfigurationError):
        gate.collect([tmp_path / "empty"])


def test_no_root_at_all_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(gate.ConfigurationError):
        gate.collect([tmp_path / "does-not-exist"])


def test_missing_frontmatter_is_a_configuration_error(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "r", "t", "# just a heading\n")
    with pytest.raises(gate.ConfigurationError):
        gate.collect([root])


def test_unclosed_frontmatter_is_a_configuration_error(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "r", "t", "---\nname: t\ndescription: X\n")
    with pytest.raises(gate.ConfigurationError):
        gate.collect([root])


def test_configuration_error_exits_two_not_zero(tmp_path: Path) -> None:
    """The exit code matters more than the exception: CI reads the code."""
    (tmp_path / "empty").mkdir()
    assert gate.main(["--root", str(tmp_path / "empty")]) == gate.EXIT_CONFIG


def test_absent_pyyaml_is_a_configuration_error_not_a_pass(monkeypatch) -> None:
    """Without the strict parser the gate can measure nothing, so it must refuse.

    Downgrading to "cannot check, therefore clean" is the no-op-gate shape
    ``rules/common/ci-hygiene.md`` forbids.
    """
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(gate.ConfigurationError):
        gate._strict_parse("name: t\n")


# --------------------------------------------------------------------------
# WIRING, with its own red proof.  A gate nothing invokes is a script, not a gate.
# --------------------------------------------------------------------------


def test_the_gate_is_wired_into_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    missing = [marker for marker in WORKFLOW_MARKERS if marker not in text]
    assert not missing, f"{WORKFLOW} no longer invokes: {missing}"


@pytest.mark.parametrize("marker", WORKFLOW_MARKERS)
def test_removing_a_wire_turns_the_wiring_check_red(
    marker: str, tmp_path: Path
) -> None:
    """The red proof for the wiring assertion itself.

    Without this, ``test_the_gate_is_wired_into_ci`` could be a tautology that
    passes against any file; this shows it fails the moment the wire is cut.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert marker in text
    mutated = tmp_path / "skill-dual-write.yml"
    mutated.write_text(
        text.replace(marker, "echo cut-wire"), encoding="utf-8", newline=""
    )
    remaining = mutated.read_text(encoding="utf-8")
    assert marker not in remaining, "the mutation did not cut the wire it targeted"
    still_missing = [m for m in WORKFLOW_MARKERS if m not in remaining]
    assert marker in still_missing


def test_the_gate_module_is_executable_as_a_cli() -> None:
    """``python -m X`` / ``python X.py`` is a no-op without a real entry point."""
    proc = subprocess.run(
        [sys.executable, str(GATE), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == gate.EXIT_OK, proc.stderr
    assert '"violations"' in proc.stdout


def test_terminal_marker_is_emitted() -> None:
    """AGENTS.md 4: a gate must end in a terminal SUCCESS:/FAILED: line."""
    proc = subprocess.run(
        [sys.executable, str(GATE)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert "SUCCESS:skill-render-traps" in proc.stdout
