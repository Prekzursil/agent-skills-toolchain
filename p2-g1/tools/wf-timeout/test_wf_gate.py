#!/usr/bin/env python3
"""Tests for ``wf_gate.py`` -- the invocation that turns workflow_lint into a gate.

Every test here is BOTH-STATES: the gate is fed a known-bad tree and required to go
RED, then a clean tree and required to go GREEN. A gate that has never gone red is
indistinguishable from a no-op, and this repo has shipped exactly that defect more
than once.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wf_gate  # noqa: E402

BAD = "prose\n```js\nconst fs = require('fs')\nconst t = Date.now()\n```\n"
CLEAN = "prose\n```js\nconst t = ts\n```\n"
BARE_BARRIER = (
    "prose\n```js\n"
    "const r = (await parallel(u.map((x) => () => agent(x, {schema: S}))))"
    ".filter(Boolean)\n"
    "```\n"
)


def _tree(root: Path, name: str, body: str) -> Path:
    d = root / "skills" / "workflow-demo" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_gate_goes_red_on_a_known_bad_block(tmp_path: Path) -> None:
    _tree(tmp_path, "bad.md", BAD)
    assert wf_gate.main(["--root", str(tmp_path)]) == 1


def test_gate_goes_green_on_a_clean_block(tmp_path: Path) -> None:
    _tree(tmp_path, "ok.md", CLEAN)
    assert wf_gate.main(["--root", str(tmp_path)]) == 0


def test_gate_fails_closed_on_an_empty_walk(tmp_path: Path) -> None:
    """An empty walk must FAIL, never silently pass -- ci-hygiene.md rule 1."""
    assert wf_gate.main(["--root", str(tmp_path)]) == 1


def test_strict_promotes_a_warning_to_a_failure(tmp_path: Path) -> None:
    _tree(tmp_path, "warn.md", BARE_BARRIER)
    assert wf_gate.main(["--root", str(tmp_path)]) == 0
    assert wf_gate.main(["--root", str(tmp_path), "--strict"]) == 1


def test_h6_rule_is_what_fires_on_the_bare_barrier(tmp_path: Path) -> None:
    _tree(tmp_path, "warn.md", BARE_BARRIER)
    blocks = wf_gate.discover_blocks(tmp_path)
    checks = {f.check for f in wf_gate.lint_blocks(blocks, tmp_path)}
    assert "barrier-without-timeout" in checks


def test_discovery_finds_every_fenced_block(tmp_path: Path) -> None:
    _tree(tmp_path, "two.md", CLEAN + "\nmore\n```js\nconst z = 1\n```\n")
    assert len(wf_gate.discover_blocks(tmp_path)) == 2


def test_discovery_ignores_non_js_fences(tmp_path: Path) -> None:
    _tree(tmp_path, "other.md", "prose\n```python\nimport os\n```\n")
    assert wf_gate.discover_blocks(tmp_path) == []


# --------------------------------------------------------------------------- #
# WS-3: discovery originally stopped at templates/*.md, so the authoring skill's
# own SKILL.md quick-start examples fired barrier-without-timeout under the
# skill's own linter and no gate ever saw them. Both states of the extended
# surface: a workflow-* SKILL.md IS walked (and its findings surface), a
# SKILL.md outside workflow-* skills is NOT.
# --------------------------------------------------------------------------- #
def test_discovery_includes_workflow_skill_md_blocks(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "workflow-demo"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(BARE_BARRIER, encoding="utf-8")
    blocks = wf_gate.discover_blocks(tmp_path)
    assert [b.path.name for b in blocks] == ["SKILL.md"]
    checks = {f.check for f in wf_gate.lint_blocks(blocks, tmp_path)}
    assert "barrier-without-timeout" in checks


def test_discovery_ignores_skill_md_outside_workflow_skills(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "other-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(BAD, encoding="utf-8")
    assert wf_gate.discover_blocks(tmp_path) == []


def test_discovery_walks_both_surfaces_of_one_skill(tmp_path: Path) -> None:
    _tree(tmp_path, "frag.md", CLEAN)
    skill_md = tmp_path / "skills" / "workflow-demo" / "SKILL.md"
    skill_md.write_text(CLEAN, encoding="utf-8")
    names = sorted(b.path.name for b in wf_gate.discover_blocks(tmp_path))
    assert names == ["SKILL.md", "frag.md"]


def test_block_outside_root_still_labels(tmp_path: Path) -> None:
    """The relative_to fallback path (self-test tmp trees live outside REPO_ROOT)."""
    p = _tree(tmp_path, "x.md", BAD)
    blocks = [wf_gate.Block(p, 0, "const t = Date.now()\n")]
    findings = wf_gate.lint_blocks(blocks, Path("C:/definitely/not/a/parent"))
    assert findings and p.as_posix() in findings[0].path


def test_self_test_passes() -> None:
    """The gate's own both-states control must be green."""
    assert wf_gate.self_test() == 0


def test_lint_live_is_empty_when_the_dir_is_absent(tmp_path: Path) -> None:
    assert wf_gate.lint_live(tmp_path / "nope") == []


def test_lint_live_reads_a_real_directory(tmp_path: Path) -> None:
    (tmp_path / "wf.mjs").write_text("const t = Date.now()\n", encoding="utf-8")
    checks = {f.check for f in wf_gate.lint_live(tmp_path)}
    assert "no-date-now" in checks


def test_live_flag_adds_the_live_tree(tmp_path: Path, monkeypatch) -> None:
    _tree(tmp_path, "ok.md", CLEAN)
    home = tmp_path / "home"
    (home / ".claude" / "workflows").mkdir(parents=True)
    (home / ".claude" / "workflows" / "bad.mjs").write_text(
        "const t = Date.now()\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert wf_gate.main(["--root", str(tmp_path), "--live"]) == 1


def test_live_flag_tolerates_a_missing_live_tree(tmp_path: Path, monkeypatch) -> None:
    _tree(tmp_path, "ok.md", CLEAN)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nohome"))
    assert wf_gate.main(["--root", str(tmp_path), "--live"]) == 0


def test_self_test_flag_is_routed(capsys: pytest.CaptureFixture[str]) -> None:
    assert wf_gate.main(["--self-test"]) == 0
    assert "SUCCESS:wf-gate-self-test" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# The detector OF the detector: self_test() must itself go red when the gate it
# is checking is broken. Without these, self_test() could return 0 for a gate
# that had stopped working -- a probe silent in both states.
# --------------------------------------------------------------------------- #
def test_self_test_fails_when_discovery_finds_nothing(monkeypatch) -> None:
    monkeypatch.setattr(wf_gate, "discover_blocks", lambda root: [])
    assert wf_gate.self_test() == 1


def test_self_test_fails_when_the_bad_block_does_not_fire(monkeypatch) -> None:
    monkeypatch.setattr(wf_gate, "lint_blocks", lambda blocks, root=None: [])
    assert wf_gate.self_test() == 1


def test_self_test_fails_when_the_clean_block_warns(monkeypatch) -> None:
    real = wf_gate.lint_blocks
    calls = {"n": 0}

    def noisy(blocks, root=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(blocks, root)
        return [wf_gate.wl.Finding("x", 1, "warn", "bogus", "injected")]

    monkeypatch.setattr(wf_gate, "lint_blocks", noisy)
    assert wf_gate.self_test() == 1


def test_self_test_fails_when_the_empty_walk_does_not_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(wf_gate, "_report", lambda findings, strict, scanned: 0)
    assert wf_gate.self_test() == 1


def test_repo_doc_blocks_are_error_free() -> None:
    """The real repo tree: zero ERRORs across every shipped doc block.

    Discovery covers both surfaces since WS-3: templates/*.md and SKILL.md.
    """
    blocks = wf_gate.discover_blocks(wf_gate.REPO_ROOT)
    assert blocks, "discovery found no doc blocks in the repo"
    errors = [f for f in wf_gate.lint_blocks(blocks) if f.level == "error"]
    assert errors == [], errors


def test_repo_skill_md_examples_are_finding_free() -> None:
    """WS-3 regression pin: the shipped SKILL.md examples model NO footgun.

    Pre-fix, the workflow-authoring SKILL.md's section-1 and rule-5 examples
    both fired barrier-without-timeout -- the exact 13h-deadlock footgun the
    skill's own rule 5b documents -- and CI never saw it because discovery
    stopped at templates/. CI runs the gate non-strict, so a WARN in a doc
    example would still pass the wf_gate step; this test is what makes the
    teaching examples warn-free by force of suite.
    """
    blocks = [
        b
        for b in wf_gate.discover_blocks(wf_gate.REPO_ROOT)
        if b.path.name == "SKILL.md"
    ]
    assert blocks, "discovery no longer sees any workflow-* SKILL.md block"
    assert wf_gate.lint_blocks(blocks) == []


def test_import_is_idempotent_when_the_lint_dir_is_already_on_the_path() -> None:
    """The one branch a single import can never reach -- and CI runs at 100%.

    ``wf_gate`` guards its ``sys.path`` insert with ``if str(_LINT_DIR) not in
    sys.path``.  The first import always takes the True arm, so the False arm
    (``36->39``) stayed a permanent branch partial.  Rather than ship the CI step
    with a coverage exception nobody would ever re-examine, re-import the module
    with the path already present and assert the guard does NOT duplicate the
    entry -- which is the behaviour the guard exists to provide.
    """
    lint_dir = str(wf_gate._LINT_DIR)
    assert lint_dir in sys.path, "the first import should have inserted it"
    before = sys.path.count(lint_dir)
    importlib.reload(wf_gate)
    assert sys.path.count(lint_dir) == before, "the guard duplicated the sys.path entry"
    # The reloaded module must still be usable, not merely importable.
    assert wf_gate.self_test() == 0
