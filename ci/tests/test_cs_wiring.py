"""Both-states proof for ``scripts/claude-science/cs_wiring_check.py``.

WHY THIS FILE EXISTS. The Claude Science lane spent three rounds fixing BROKEN WIRES -- a slash
command pointing at a stale checkout, a watchdog registered against a disposable git worktree, a
deployer hardcoded to that same stale tree, and a documented probe that ``install.ps1`` never
deployed. Every one of those fixes was, until now, enforced by a human remembering to look. This
suite is what makes the enforcement automatic, and it is what makes the enforcement CREDIBLE: a
green checker proves nothing until each of its codes has been shown to fire in the broken state.

  * ``test_the_real_repository_is_green`` is the HEALTHY control. Without it, a rule that is
    permanently red would still satisfy every mutation below.
  * ``test_mutation_turns_the_gate_red`` is the BROKEN direction: one scratch copy per mutation,
    exactly one wire cut, and the specific code must appear. Most mutations are ``exclusive``,
    meaning the cut wire must be the ONLY code that fires -- that is what separates a targeted
    rule from a rule that just goes red whenever anything is touched.
  * ``test_every_invariant_has_a_red_proof`` closes the last hole: a code with no mutation is a
    code nobody has ever seen fire, so adding one to ``CHECKS`` without a mutation fails here.

Two of these mutations exist because the checker's OWN first run was wrong, and the record is kept
deliberately rather than quietly deleted:

  * ``W6-sourcing-not-deployed`` -- the original rule asked whether a script CONTAINED the string
    ``cs-lib.sh``. ``cs-deploy.sh`` names it six times because it DEPLOYS it, so the rule demanded
    that the deployer be deployed by the thing it deploys. Use-vs-mention, in the instrument. The
    rule now reads the source statement, and this mutation proves the narrower rule still bites.
  * ``W9-config-bypass`` -- the first run flagged the checker's own ``BYPASS_PATTERNS`` table,
    which necessarily contains the literals it hunts. A probe that matches its own command line.

Run (there is no repo-wide pytest autodiscovery; ``.github/workflows/skill-dual-write.yml`` runs
``pytest ci/tests`` as a directory AND names this file explicitly)::

    python -m pytest ci/tests/test_cs_wiring.py -q
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "claude-science" / "cs_wiring_check.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
# The explicit step in the workflow. The directory glob above it would already collect this file,
# but the workflow's own comments record that the glob is one refactor away from not containing a
# given file -- so the explicit name is the durable wire, and this constant is what pins it.
WORKFLOW_STEP_MARKER = "python -m pytest ci/tests/test_cs_wiring.py -q"

sys.path.insert(0, str(CHECKER.parent))
import cs_wiring_check as wiring  # noqa: E402

# Everything the checker reads. Copied file-by-file rather than with ``shutil.copytree`` over the
# repository: a blanket recursive copy on Windows aborts mid-tree with WinError 87 the moment it
# meets a reserved device name, and it would also drag in whatever a sibling agent is writing.
COPY_PATHS = (
    "scripts/claude-science",
    "commands/claude-science.md",
    "agent-self/config/commands/claude-science.md",
    ".agents/skills/claude-science-local",
    "skills/claude-science-local",
    ".agents/skills/monitor-launcher/monitors.toml",
    "skills/monitor-launcher/monitors.toml",
)

SCIENCE_MD = (
    "commands/claude-science.md",
    "agent-self/config/commands/claude-science.md",
)
STALE = "~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1"


def _scratch(dest: Path) -> Path:
    """Build a minimal, byte-exact copy of the wiring surface under ``dest``."""
    for rel in COPY_PATHS:
        src = REPO_ROOT / rel
        assert src.exists(), f"fixture source missing: {rel}"
        out = dest / rel
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            # __pycache__ is a side effect of importing the checker out of the source tree, not
            # part of the wiring surface. Anything ELSE that is a directory is unexpected and
            # fails loudly rather than being silently skipped: a fixture that quietly stops
            # copying half the tree is a green test measuring nothing.
            children = sorted(c for c in src.iterdir() if c.name != "__pycache__")
            assert all(c.is_file() for c in children), (
                f"{rel} gained a subdirectory; update _scratch"
            )
            for child in children:
                shutil.copy2(child, out / child.name)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
    return dest


def _edit(root: Path, rel: str, old: str, new: str, *, count: int = 1) -> None:
    """Exact-match replacement that refuses to be a silent no-op.

    A mutation that quietly changes nothing produces a green run that looks like a passing test and
    is in fact a broken detector, so the anchor must match exactly ``count`` times or the test dies
    here rather than reporting a misleading verdict.
    """
    path = root / rel
    text = path.read_text(encoding="utf-8")
    hits = text.count(old)
    assert hits == count, f"anchor matched {hits}x in {rel}, expected {count}: {old!r}"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="")


def _break_route_stale(root: Path) -> None:
    for rel in SCIENCE_MD:
        _edit(root, rel, wiring.DISPATCHER, STALE)


def _break_route_absent(root: Path) -> None:
    for rel in SCIENCE_MD:
        _edit(root, rel, f"pwsh -NoProfile -File {wiring.DISPATCHER} $ARGUMENTS\n", "")


def _break_twin(root: Path) -> None:
    path = root / "agent-self/config/commands/claude-science.md"
    path.write_bytes(path.read_bytes() + b"\n")


def _break_no_alias_files(root: Path) -> None:
    for rel in wiring.RETIRED_ALIAS_COMMANDS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\ndescription: retired alias\n---\n", encoding="utf-8", newline=""
        )


def _break_no_alias_usage(root: Path) -> None:
    for rel in SCIENCE_MD:
        _edit(root, rel, "```\n/claude-science", "```\n/cs <verb>\n/claude-science")


def _break_description(root: Path) -> None:
    for rel in SCIENCE_MD:
        text = (root / rel).read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if ln.startswith("description:"))
        _edit(root, rel, line, "description:")


def _break_docs_deploy(root: Path) -> None:
    # Reverts THIS lane's install.ps1 fix. If the gate stays green here, the fix was decorative.
    _edit(
        root, "scripts/claude-science/install.ps1", ", 'test-cs-backup-readonly.py'", ""
    )


def _break_install_src(root: Path) -> None:
    (root / "scripts/claude-science/cs-start.cmd").unlink()


def _break_seam_keep(root: Path) -> None:
    _edit(
        root,
        "scripts/claude-science/install.ps1",
        "foreach ($f in 'cs-lib.sh', 'cs.conf')",
        "foreach ($f in 'cs.conf')",
    )


def _break_seam_sourcing(root: Path) -> None:
    _edit(root, "scripts/claude-science/install.ps1", "'cs-backup.sh', ", "")


def _break_deploy_src(root: Path) -> None:
    _edit(
        root,
        "scripts/claude-science/cs-deploy.sh",
        'SRC="${CS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"',
        "SRC=/mnt/c/Users/Prekzursil/source/agent-skills-toolchain/scripts/claude-science",
    )


def _break_monitor_duplicate(root: Path) -> None:
    path = root / ".agents/skills/monitor-launcher/monitors.toml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + '\n[csmon]\ndir = "claude-science-local"\nentry = "cs_monitor.py"\n',
        encoding="utf-8",
        newline="",
    )


def _break_monitor_target(root: Path) -> None:
    _edit(
        root,
        "skills/monitor-launcher/monitors.toml",
        'entry = "cs_monitor.py"',
        'entry = "gone.py"',
    )


def _break_config_bypass(root: Path) -> None:
    path = root / "scripts/claude-science/cs.ps1"
    path.write_text(
        path.read_text(encoding="utf-8") + '\n$fallback = "http://127.0.0.1:8000/"\n',
        encoding="utf-8",
        newline="",
    )


def _break_sh_eol(root: Path) -> None:
    path = root / "scripts/claude-science/cs-backup.sh"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))


def _break_gitattributes(root: Path) -> None:
    (root / "scripts/claude-science/.gitattributes").unlink()


# code, id, exclusive, mutation
MUTATIONS: tuple[tuple[str, str, bool, Callable[[Path], None]], ...] = (
    ("W1-route", "route-points-at-a-stale-checkout", True, _break_route_stale),
    ("W1-route", "route-invocation-deleted-entirely", True, _break_route_absent),
    ("W2-twin", "dual-written-twin-drifts", True, _break_twin),
    ("W3-description", "frontmatter-description-blanked", True, _break_description),
    ("W4-docs-deploy", "documented-probe-not-in-deploy-list", True, _break_docs_deploy),
    ("W5-install-src", "deployed-name-has-no-source-file", True, _break_install_src),
    ("W6-seam-deploy", "seam-file-dropped-from-keep-loop", True, _break_seam_keep),
    ("W6-seam-deploy", "sourcing-script-not-deployed", True, _break_seam_sourcing),
    ("W7-deploy-src", "deployer-pinned-to-a-fixed-checkout", True, _break_deploy_src),
    ("W8-monitor", "duplicate-csmon-stanza", True, _break_monitor_duplicate),
    ("W8-monitor", "csmon-entry-file-missing", True, _break_monitor_target),
    ("W9-config-bypass", "port-hardcoded-outside-the-seam", True, _break_config_bypass),
    ("W10-sh-eol", "shell-script-rewritten-as-crlf", True, _break_sh_eol),
    ("W10-sh-eol", "gitattributes-eol-pin-removed", True, _break_gitattributes),
    ("W11-no-alias", "retired-alias-files-restored", True, _break_no_alias_files),
    ("W11-no-alias", "retired-alias-usage-restored", True, _break_no_alias_usage),
)


def test_the_real_repository_is_green() -> None:
    """HEALTHY control. Without this, a permanently-red rule would satisfy every mutation."""
    violations = wiring.check(REPO_ROOT)
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize(
    ("code", "exclusive", "mutate"),
    [(c, x, m) for c, _, x, m in MUTATIONS],
    ids=[i for _, i, _, _ in MUTATIONS],
)
def test_mutation_turns_the_gate_red(
    tmp_path: Path, code: str, exclusive: bool, mutate: Callable[[Path], None]
) -> None:
    root = _scratch(tmp_path / "repo")
    assert wiring.check(root) == [], (
        "the scratch copy must start green or the mutation proves nothing"
    )
    mutate(root)
    violations = wiring.check(root)
    codes = {v.code for v in violations}
    assert code in codes, (
        f"{code} did not fire; got {sorted(codes) or 'nothing at all'}"
    )
    if exclusive:
        assert codes == {code}, (
            f"mutation was meant to be surgical but also tripped {sorted(codes - {code})}"
        )


def test_every_invariant_has_a_red_proof() -> None:
    """A code with no mutation is a code nobody has ever watched fire."""
    proven = {c for c, _, _, _ in MUTATIONS}
    assert proven == set(wiring.CHECKS), (
        f"unproven: {sorted(set(wiring.CHECKS) - proven)}"
    )


def test_cannot_measure_is_not_a_pass(tmp_path: Path) -> None:
    """An unmeasurable root must say so, never render green. Same rule as the doctor's NOT-CHECKED."""
    with pytest.raises(wiring.CannotMeasure):
        wiring.check(tmp_path)


@pytest.mark.parametrize(
    ("prepare", "expected_code", "marker"),
    [
        (lambda root: None, 0, "SUCCESS:cs-wiring"),
        (_break_route_stale, 1, "FAILED:cs-wiring"),
    ],
)
def test_cli_contract(
    tmp_path: Path, prepare: Callable[[Path], None], expected_code: int, marker: str
) -> None:
    root = _scratch(tmp_path / "repo")
    prepare(root)
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == expected_code, proc.stdout + proc.stderr
    assert marker in proc.stdout + proc.stderr


def test_cli_reports_not_checked_on_a_foreign_root(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "NOT-CHECKED:cs-wiring" in proc.stdout + proc.stderr


def test_the_gate_is_actually_wired_into_ci() -> None:
    """A gate nobody runs is not a gate. Moving or renaming either side must fail loudly here."""
    assert WORKFLOW.is_file(), (
        "skill-dual-write.yml is gone; this suite is no longer invoked"
    )
    assert WORKFLOW_STEP_MARKER in WORKFLOW.read_text(encoding="utf-8"), (
        "the workflow no longer names this suite by explicit path"
    )
