#!/usr/bin/env python3
"""wf_gate.py -- run ``workflow_lint`` over every workflow JS block in the repo.

WHY THIS EXISTS. ``skills/workflow-authoring/scripts/workflow_lint.py`` was shipped
with 110 tests and a 100%-coverage CI lane -- and **nothing ran it over any actual
workflow source**. A linter no gate invokes is a no-op, which is the exact defect
class this repo keeps re-shipping. This module is the invocation.

WHAT IT LINTS. The saved workflows themselves live at ``~/.claude/workflows`` and are
machine-local, so CI cannot see them. What CI *can* see is every fenced ``js`` block
inside ``skills/workflow-*/templates/*.md`` -- the code the skill tells authors to
paste. Those are linted here. Use ``--live`` on a workstation to additionally lint
the real saved workflows.

FAIL-CLOSED (rules/common/ci-hygiene.md 1). Discovering zero blocks is a FAILURE, not
a pass: an empty walk is how a gate silently stops checking anything.

    python wf_gate.py                     # lint the repo's template blocks
    python wf_gate.py --strict            # warnings are failures too
    python wf_gate.py --live              # also lint ~/.claude/workflows
    python wf_gate.py --self-test         # prove the gate goes RED on a bad block
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
_LINT_DIR = REPO_ROOT / "skills" / "workflow-authoring" / "scripts"
if str(_LINT_DIR) not in sys.path:
    sys.path.insert(0, str(_LINT_DIR))

import workflow_lint as wl  # noqa: E402

# ``\n```js\n ... \n```\n`` -- the same shape the skill's own suite already uses.
_JS_BLOCK = re.compile(r"\n```js\n(.*?)\n```\n", re.S)

# A template block is a FRAGMENT pasted into a workflow, so it legitimately has no
# `export const meta` of its own. Prepend one before linting rather than teaching
# the linter an exception it would then apply to real workflows too.
_META_STUB = "export const meta = { name: 'template-fragment', description: 'x' }\n"


@dataclass(frozen=True)
class Block:
    """One fenced ``js`` block found in a markdown template."""

    path: Path
    index: int
    source: str


def discover_blocks(root: Path) -> list[Block]:
    """Every fenced ``js`` block under ``skills/workflow-*/templates/*.md``."""
    blocks: list[Block] = []
    for template in sorted((root / "skills").glob("workflow-*/templates/*.md")):
        text = template.read_text(encoding="utf-8")
        for i, body in enumerate(_JS_BLOCK.findall(text)):
            blocks.append(Block(template, i, body))
    return blocks


def lint_blocks(blocks: Sequence[Block], root: Path = REPO_ROOT) -> list[wl.Finding]:
    """Lint each block with a meta stub prepended; line numbers stay 1-based."""
    findings: list[wl.Finding] = []
    for block in blocks:
        try:
            shown = block.path.relative_to(root).as_posix()
        except ValueError:  # a block outside `root` (self-test tmp tree)
            shown = block.path.as_posix()
        label = f"{shown}#js[{block.index}]"
        findings.extend(wl.lint_text(_META_STUB + block.source, label))
    return findings


def lint_live(live_root: Path) -> list[wl.Finding]:
    """Lint the machine-local saved workflows, if that directory exists."""
    if not live_root.is_dir():
        return []
    return [
        f for p in wl.iter_workflow_files([str(live_root)]) for f in wl.lint_file(p)
    ]


def _report(findings: Sequence[wl.Finding], strict: bool, scanned: int) -> int:
    for finding in findings:
        print(wl.format_finding(finding))
    errors = sum(1 for f in findings if f.level == wl.ERROR)
    warnings = len(findings) - errors
    if scanned == 0:
        print("FAILED:wf-gate discovered ZERO workflow blocks (empty walk)")
        return 1
    failed = errors > 0 or (strict and warnings > 0)
    verdict = "FAILED" if failed else "SUCCESS"
    print(
        f"{verdict}:wf-gate {errors} error(s), {warnings} warning(s) "
        f"across {scanned} block(s)"
    )
    return 1 if failed else 0


_BAD_BLOCK = "\n```js\nconst fs = require('fs')\nconst t = Date.now()\n```\n"


def self_test() -> int:
    """Both-states control: the gate MUST go red on a deliberately bad block.

    A gate that has never gone red is indistinguishable from a no-op, so this runs
    the real discovery+lint path over a synthetic tree containing one known-bad
    block and one known-good block, and requires red then green.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tdir = root / "skills" / "workflow-broken" / "templates"
        tdir.mkdir(parents=True)
        (tdir / "bad.md").write_text(f"prose{_BAD_BLOCK}", encoding="utf-8")

        bad = discover_blocks(root)
        if len(bad) != 1:
            print(f"FAILED:wf-gate-self-test discovery found {len(bad)} blocks, want 1")
            return 1
        checks = {f.check for f in lint_blocks(bad, root)}
        want = {"sandbox-forbidden", "no-date-now"}
        if not want <= checks:
            print(
                f"FAILED:wf-gate-self-test broken block did not fire {want}: {checks}"
            )
            return 1

        (tdir / "bad.md").write_text(
            "prose\n```js\nconst t = ts\n```\n", encoding="utf-8"
        )
        clean = lint_blocks(discover_blocks(root), root)
        if clean:
            print(f"FAILED:wf-gate-self-test clean block produced {clean}")
            return 1

    empty = _report([], strict=False, scanned=0)
    if empty != 1:
        print("FAILED:wf-gate-self-test empty walk did not fail closed")
        return 1
    print("SUCCESS:wf-gate-self-test red on bad, green on clean, closed on empty")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wf_gate")
    parser.add_argument("--strict", action="store_true", help="warnings fail too")
    parser.add_argument(
        "--live", action="store_true", help="also lint ~/.claude/workflows"
    )
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--self-test", action="store_true")
    ns = parser.parse_args(argv)
    if ns.self_test:
        return self_test()

    root = Path(ns.root)
    blocks = discover_blocks(root)
    findings = lint_blocks(blocks, root)
    scanned = len(blocks)
    if ns.live:
        live = Path.home() / ".claude" / "workflows"
        live_findings = lint_live(live)
        findings.extend(live_findings)
        scanned += len(wl.iter_workflow_files([str(live)])) if live.is_dir() else 0
    return _report(findings, ns.strict, scanned)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
